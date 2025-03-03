from datetime import datetime
from flask import request
from flask_restful import abort, Api, Resource
from logging import info
from psutil import cpu_percent
from uuid import getnode

from eNMS import app
from eNMS.database import Session
from eNMS.database.functions import delete, factory, fetch
from eNMS.framework.extensions import auth, csrf


def create_app_resources():
    endpoints = {}
    for endpoint in app.rest_endpoints:

        def post(_, ep=endpoint):
            getattr(app, ep)()
            Session.commit()
            return f"Endpoint {ep} successfully executed."

        endpoints[endpoint] = type(
            endpoint, (Resource,), {"decorators": [auth.login_required], "post": post}
        )
    return endpoints


class CreatePool(Resource):
    decorators = [auth.login_required]

    def post(self):
        data = request.get_json(force=True)
        factory(
            "pool",
            **{
                "name": data["name"],
                "devices": [
                    fetch("device", name=name).id for name in data.get("devices", "")
                ],
                "links": [
                    fetch("link", name=name).id for name in data.get("links", "")
                ],
                "never_update": True,
            },
        )
        Session.commit()
        return data


class Heartbeat(Resource):
    def get(self):
        return {
            "name": getnode(),
            "cluster_id": app.config["cluster"]["id"],
            "cpu_load": cpu_percent(),
        }


class Query(Resource):
    decorators = [auth.login_required]

    def get(self, cls):
        try:
            results = fetch(cls, all_matches=True, **request.args.to_dict())
            return [result.get_properties(exclude=["positions"]) for result in results]
        except Exception:
            return abort(404, message=f"There are no such {cls}s.")


class GetInstance(Resource):
    decorators = [auth.login_required]

    def get(self, cls, name):
        try:
            return fetch(cls, name=name).to_dict(
                relation_names_only=True, exclude=["positions"]
            )
        except Exception:
            return abort(404, message=f"{cls} {name} not found.")

    def delete(self, cls, name):
        result = delete(cls, name=name)
        Session.commit()
        return result


class GetConfiguration(Resource):
    decorators = [auth.login_required]

    def get(self, name):
        return fetch("device", name=name).configuration


class GetResult(Resource):
    decorators = [auth.login_required]

    def get(self, name, runtime):
        service = fetch("service", name=name)
        return fetch("result", service_id=service.id, runtime=runtime).result


class UpdateInstance(Resource):
    decorators = [auth.login_required]

    def post(self, cls):
        try:
            data = request.get_json(force=True)
            object_data = app.objectify(cls, data)
            result = factory(cls, **object_data).serialized
            Session.commit()
            return result
        except Exception as exc:
            return abort(500, message=f"Update failed ({exc})")


class Migrate(Resource):
    decorators = [auth.login_required]

    def post(self, direction):
        kwargs = request.get_json(force=True)
        return getattr(app, f"migration_{direction}")(**kwargs)


class RunService(Resource):
    decorators = [auth.login_required]

    def post(self):
        try:
            errors, data = [], request.get_json(force=True)
            devices, pools = [], []
            service = fetch("service", name=data["name"])
            handle_asynchronously = data.get("async", False)
            for device_name in data.get("devices", ""):
                device = fetch("device", name=device_name)
                if device:
                    devices.append(device.id)
                else:
                    errors.append(f"No device with the name '{device_name}'")
            for device_ip in data.get("ip_addresses", ""):
                device = fetch("device", ip_address=device_ip)
                if device:
                    devices.append(device.id)
                else:
                    errors.append(f"No device with the IP address '{device_ip}'")
            for pool_name in data.get("pools", ""):
                pool = fetch("pool", name=pool_name)
                if pool:
                    pools.append(pool.id)
                else:
                    errors.append(f"No pool with the name '{pool_name}'")
            if errors:
                return {"errors": errors}
        except Exception as e:
            info(f"REST API run_service endpoint failed ({str(e)})")
            return str(e)
        if devices or pools:
            data.update({"devices": devices, "pools": pools})
        data["runtime"] = runtime = app.get_time()
        if handle_asynchronously:
            app.scheduler.add_job(
                id=runtime,
                func=app.run,
                run_date=datetime.now(),
                args=[service.id],
                kwargs=data,
                trigger="date",
            )
            return {"errors": errors, "runtime": runtime}
        else:
            return {**app.run(service.id, **data), "errors": errors}


class Topology(Resource):
    decorators = [auth.login_required]

    def post(self, direction):
        if direction == "import":
            return app.import_topology(
                **{
                    "replace": request.form["replace"] == "True",
                    "file": request.files["file"],
                }
            )
        else:
            app.export_topology(**request.get_json(force=True))
            return "Topology Export successfully executed."


def configure_rest_api(flask_app):
    api = Api(flask_app, decorators=[csrf.exempt])
    for endpoint, resource in create_app_resources().items():
        api.add_resource(resource, f"/rest/{endpoint}")
    api.add_resource(CreatePool, "/rest/create_pool")
    api.add_resource(Heartbeat, "/rest/is_alive")
    api.add_resource(RunService, "/rest/run_service")
    api.add_resource(Query, "/rest/query/<string:cls>")
    api.add_resource(UpdateInstance, "/rest/instance/<string:cls>")
    api.add_resource(GetInstance, "/rest/instance/<string:cls>/<string:name>")
    api.add_resource(GetConfiguration, "/rest/configuration/<string:name>")
    api.add_resource(GetResult, "/rest/result/<string:name>/<string:runtime>")
    api.add_resource(Migrate, "/rest/migrate/<string:direction>")
    api.add_resource(Topology, "/rest/topology/<string:direction>")
