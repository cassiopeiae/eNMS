from sqlalchemy import Boolean, Float, ForeignKey, Integer
from wtforms import BooleanField, HiddenField

from eNMS.database.dialect import Column, LargeString, SmallString
from eNMS.forms.fields import SubstitutionField
from eNMS.forms.automation import NetmikoForm
from eNMS.models.automation import ConnectionService


class NetmikoValidationService(ConnectionService):

    __tablename__ = "netmiko_validation_service"
    pretty_name = "Netmiko Validation"
    parent_type = "connection_service"
    id = Column(Integer, ForeignKey("connection_service.id"), primary_key=True)
    enable_mode = Column(Boolean, default=True)
    config_mode = Column(Boolean, default=False)
    command = Column(LargeString)
    driver = Column(SmallString)
    use_device_driver = Column(Boolean, default=True)
    fast_cli = Column(Boolean, default=False)
    timeout = Column(Float, default=10.0)
    delay_factor = Column(Float, default=1.0)
    global_delay_factor = Column(Float, default=1.0)
    expect_string = Column(SmallString)
    auto_find_prompt = Column(Boolean, default=True)
    strip_prompt = Column(Boolean, default=True)
    strip_command = Column(Boolean, default=True)

    __mapper_args__ = {"polymorphic_identity": "netmiko_validation_service"}

    def job(self, run, payload, device):
        netmiko_connection = run.netmiko_connection(device)
        command = run.sub(run.command, locals())
        run.log("info", f"Sending '{run.command}' with Netmiko", device)
        expect_string = run.sub(run.expect_string, locals())
        result = netmiko_connection.send_command(
            command,
            delay_factor=run.delay_factor,
            expect_string=run.expect_string or None,
            auto_find_prompt=run.auto_find_prompt,
            strip_prompt=run.strip_prompt,
            strip_command=run.strip_command,
        )
        return {"command": command, "result": result}


class NetmikoValidationForm(NetmikoForm):
    form_type = HiddenField(default="netmiko_validation_service")
    command = SubstitutionField()
    expect_string = SubstitutionField()
    auto_find_prompt = BooleanField(default=True)
    strip_prompt = BooleanField(default=True)
    strip_command = BooleanField(default=True)
    groups = {
        "Main Parameters": {"commands": ["command"], "default": "expanded"},
        "Advanced Netmiko Parameters": {
            "commands": [
                "expect_string",
                "auto_find_prompt",
                "strip_prompt",
                "strip_command",
            ],
            "default": "hidden",
        },
        **NetmikoForm.groups,
    }
