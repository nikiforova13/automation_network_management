import ipaddress
from scrapli import Scrapli

from app.config.driver import driver, device
from app.config.device_config import path_config_parse, template
from app.routers.api_schemas.configuration import DeviceConfigurationData
from app.enums import commands, configurations
from scrapli.response import Response as ScrapliResponse
from fastapi.exceptions import ResponseValidationError, HTTPException
from fastapi.responses import Response
from app.logger import logger


async def _parse_config(config: ScrapliResponse):
    return config.ttp_parse_output(str(path_config_parse))[0]


def _settings_driver(hostname: str):
    device_settings = device._devices
    driver_settings = driver._settings

    if driver_settings.get("host") is None:
        host = device_settings.get(hostname)
        driver_settings.update({"host": host})
    return driver_settings


async def get_device_configuration(
    hostname: str,
    command: commands.ShowCommandCisco | None = None,
) -> DeviceConfigurationData:
    if not command:
        command = commands.ShowCommandCisco.ALL_CONFIG
    logger.info(f"Getting configurations with {hostname}")
    with Scrapli(**_settings_driver(hostname)) as ssh:
        data = ssh.send_command(command)
        if data.failed:
            # return ResponseValidationError(errors='Команда не была успешно обработана')
            raise HTTPException(
                status_code=503,
                detail=f"Команда {command} не была успешно обработана на устройстве",
            )
        logger.info("The configuration has been successfully received")
        config = await _parse_config(config=data)
        return DeviceConfigurationData(**config).model_dump()


async def configure_device(
    hostname: str,
    params: DeviceConfigurationData,
    action: configurations.Action | None = configurations.Action.create,
):
    configurations = params.configuration.model_dump(exclude_none=True)
    cmds = template.render(configurations, action=action).split("\n")
    cmds.remove("")
    logger.info(f"Device {hostname} configuring {cmds}")
    with Scrapli(**_settings_driver(hostname)) as ssh:
        res = ssh.send_configs(
            cmds,
        )

        if res.failed:
            raise HTTPException(
                status_code=503,
                detail=f"Во время конфигурации устройства произошла ошибка",
            )
        logger.info(f"The device {hostname} has been successfully configured")
        return Response(status_code=200, content="Successful Response")


def subnet_masks_with_prefix():
    subnet_masks = []
    for prefix_length in range(33):
        network = ipaddress.IPv4Network(("0.0.0.0", prefix_length), strict=False)
        subnet_masks.append(f"{str(network.netmask)} /{prefix_length}")
    return subnet_masks
