from copy import deepcopy
from flask_login import current_user
from ipaddress import IPv4Network
from json import loads
from logging import info
from ldap3 import Connection, NTLM, SUBTREE
from os import listdir, makedirs
from os.path import exists
from pathlib import Path
from shutil import rmtree
from requests import get as http_get
from ruamel import yaml
from tarfile import open as open_tar
from traceback import format_exc

from eNMS.controller.base import BaseController
from eNMS.database import Session
from eNMS.database.functions import delete_all, export, factory, fetch, fetch_all
from eNMS.models import relationships


class AdministrationController(BaseController):
    def authenticate_user(self, **kwargs):
        name, password = kwargs["name"], kwargs["password"]
        if kwargs["authentication_method"] == "Local User":
            user = fetch("user", allow_none=True, name=name)
            return user if user and password == user.password else False
        elif kwargs["authentication_method"] == "LDAP Domain":
            with Connection(
                self.ldap_client,
                user=f"{self.ldap_userdn}\\{name}",
                password=password,
                auto_bind=True,
                authentication=NTLM,
            ) as connection:
                connection.search(
                    self.ldap_basedn,
                    f"(&(objectClass=person)(samaccountname={name}))",
                    search_scope=SUBTREE,
                    get_operational_attributes=True,
                    attributes=["cn", "memberOf", "mail"],
                )
                json_response = loads(connection.response_to_json())["entries"][0]
                if json_response and any(
                    group in s
                    for group in self.ldap_admin_group.split(",")
                    for s in json_response["attributes"]["memberOf"]
                ):
                    user = factory(
                        "user",
                        **{
                            "name": name,
                            "password": password,
                            "email": json_response["attributes"].get("mail", ""),
                        },
                    )
        elif kwargs["authentication_method"] == "TACACS":
            if self.tacacs_client.authenticate(name, password).valid:
                user = factory("user", **{"name": name, "password": password})
        Session.commit()
        return user

    def get_user_credentials(self):
        return (current_user.name, current_user.password)

    def database_deletion(self, **kwargs):
        delete_all(*kwargs["deletion_types"])

    def get_cluster_status(self):
        return {
            attr: [getattr(server, attr) for server in fetch_all("server")]
            for attr in ("status", "cpu_load")
        }

    def objectify(self, model, obj):
        for property, relation in relationships[model].items():
            if property not in obj:
                continue
            elif relation["list"]:
                obj[property] = [
                    fetch(relation["model"], name=name).id for name in obj[property]
                ]
            else:
                obj[property] = fetch(relation["model"], name=obj[property]).id
        return obj

    def migration_import(self, folder="migrations", **kwargs):
        status, models = "Import successful.", kwargs["import_export_types"]
        if kwargs.get("empty_database_before_import", False):
            for model in models:
                delete_all(model)
                Session.commit()
        workflow_edges, workflow_services = [], {}
        folder_path = self.path / "projects" / folder / kwargs["name"]
        for model in models:
            path = folder_path / f"{model}.yaml"
            if not path.exists():
                continue
            with open(path, "r") as migration_file:
                instances = yaml.load(migration_file)
                if model == "workflow_edge":
                    workflow_edges = deepcopy(instances)
                    continue
                for instance in instances:
                    instance_type = (
                        instance.pop("type") if model == "service" else model
                    )
                    if model == "service":
                        instance["scoped_name"] = instance["name"]
                    if instance_type == "workflow":
                        instance.pop("start_services")
                        workflow_services[instance["name"]] = instance.pop("services")
                    try:
                        instance = self.objectify(instance_type, instance)
                        factory(instance_type, **instance)
                        Session.commit()
                    except Exception as e:
                        info(
                            f"{str(instance)} could not be imported :"
                            f"{chr(10).join(format_exc().splitlines())}"
                        )
                        status = "Partial import (see logs)."
        for name, services in workflow_services.items():
            workflow = fetch("workflow", name=name)
            for service_name in services:
                try:
                    workflow.services.append(
                        fetch("service", name=service_name)
                    )
                except Exception as exc:
                    print(exc)
        Session.commit()
        for edge in workflow_edges:
            for property in ("source", "destination", "workflow"):
                edge[property] = fetch("service", name=edge[property]).id
            edge.pop("name", None)
            factory("workflow_edge", **edge)
            Session.commit()
        new_names = {}
        for service in fetch_all("service"):
            new_name = new_names[service.name] = service.build_name()
            service.name = new_name
        Session.commit()
        print(new_names)
        try:
            for service in fetch_all("service"):
                for workflow_name in deepcopy(service.positions):
                    if workflow_name not in new_names:
                        service.positions.pop(workflow_name)
                        continue
                    print(service.name, new_names[workflow_name], service.positions[workflow_name])
                    service.positions[new_names[workflow_name]] = service.positions[workflow_name]
        except Exception as exc:
            info(exc)
        Session.commit()
        return status

    def import_service(self, archive):
        service_name = archive.split(".")[0]
        path = self.path / "projects" / "services"
        with open_tar(path / archive) as tar_file:
            tar_file.extractall(path=path)
            status = self.migration_import(
                folder="services",
                name=service_name,
                import_export_types=["service", "workflow_edge"],
            )
        rmtree(path / service_name)
        return status

    def migration_export(self, **kwargs):
        for cls_name in kwargs["import_export_types"]:
            path = self.path / "projects" / "migrations" / kwargs["name"]
            if not exists(path):
                makedirs(path)
            with open(path / f"{cls_name}.yaml", "w") as migration_file:
                yaml.dump(export(cls_name), migration_file)

    def export_service(self, service_id):
        service = fetch("service", id=service_id)
        path = Path(self.path / "projects" / "services" / service.filename)
        path.mkdir(parents=True, exist_ok=True)
        services = service.deep_services if service.type == "workflow" else [service]
        services = [service.to_dict(export=True) for service in services]
        for service_dict in services:
            for relation in ("devices", "pools", "events"):
                service_dict.pop(relation)
        with open(path / f"service.yaml", "w") as file:
            yaml.dump(services, file)
        if service.type == "workflow":
            with open(path / "workflow_edge.yaml", "w") as file:
                yaml.dump(
                    [edge.to_dict(export=True) for edge in service.deep_edges], file
                )
        with open_tar(f"{path}.tgz", "w:gz") as tar:
            tar.add(path, arcname=service.filename)
        rmtree(path)

    def get_exported_services(self):
        return listdir(self.path / "projects" / "services")

    def save_parameters(self, parameter_type, **kwargs):
        self.update_parameters(**kwargs)
        if parameter_type == "git":
            self.get_git_content()

    def scan_cluster(self, **kwargs):
        for ip_address in IPv4Network(self.cluster_scan_subnet):
            try:
                server = http_get(
                    f"{self.cluster_scan_protocol}://{ip_address}/rest/is_alive",
                    timeout=self.cluster_scan_timeout,
                ).json()
                if self.cluster_id != server.pop("cluster_id"):
                    continue
                factory("server", **{**server, **{"ip_address": str(ip_address)}})
            except ConnectionError:
                continue
