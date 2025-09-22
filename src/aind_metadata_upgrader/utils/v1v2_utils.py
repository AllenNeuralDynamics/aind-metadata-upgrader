"""Shared utility functions for the AIND Metadata Upgrader."""

from typing import Optional

from aind_data_schema.components.coordinates import (
    Affine,
    CoordinateSystemLibrary,
    Scale,
    Translation,
)
from aind_data_schema.components.reagent import Reagent
from aind_data_schema.components.devices import (
    Computer,
    Device,
    Enclosure,
    Filter,
    Lamp,
    Laser,
    Lens,
    LightEmittingDiode,
    Objective,
)
from aind_data_schema.components.identifiers import Software
from aind_data_schema.components.measurements import (
    Calibration,
    CalibrationFit,
    FitType,
    PowerCalibration,
    VolumeCalibration,
)
from aind_data_schema.components.connections import (
    Connection,
)
from aind_data_schema_models.brain_atlas import CCFv3
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.registries import Registry
from aind_data_schema_models.units import (
    PowerUnit,
    SizeUnit,
    TimeUnit,
    VoltageUnit,
    VolumeUnit,
    SoundIntensityUnit,
    FrequencyUnit,
    AngleUnit,
)

MODALITY_MAP = {"SmartSPIM": Modality.SPIM, "smartspim": Modality.SPIM, "FIP": Modality.FIB}

counts = {}


def validate_frequency_unit(frequency_unit: str) -> str:
    """Validate a frequency unit and repair it if needed"""
    if frequency_unit in [member.value for member in FrequencyUnit]:
        return frequency_unit
    elif frequency_unit.lower() in [member.value for member in FrequencyUnit]:
        return frequency_unit.lower()
    else:
        print(f"Invalid frequency unit: {frequency_unit}.")
        raise NotImplementedError()


def validate_angle_unit(angle_unit: str) -> str:
    """Validate an angle unit and repair it if needed"""
    if angle_unit in [member.value for member in AngleUnit]:
        return angle_unit
    elif angle_unit.lower() in [member.value for member in AngleUnit]:
        return angle_unit.lower()
    else:
        # before we give up, check if the unit is contained in one of the units, e.g. degree in degrees
        for member in AngleUnit:
            if angle_unit.lower() in member.value.lower():
                return member.value

        print(f"Invalid angle unit: {angle_unit}.")
        raise NotImplementedError()


def upgrade_v1_modalities(data: dict) -> list:
    """Upgrade v1.x modalities lists to the v2.0 format"""

    modalities = data.get("modality", [])

    if not isinstance(modalities, list):
        if isinstance(modalities, str):
            # Coerce single modality to it's object
            if modalities in MODALITY_MAP:
                modalities = [MODALITY_MAP[modalities].model_dump()]
            else:
                # Convert try to get a Modality object from abbreviation
                try:
                    modalities = [Modality.from_abbreviation(modalities).model_dump()]
                except Exception as e:
                    raise ValueError(f"Unsupported modality abbreviation: {modalities}") from e
        else:
            modalities = [modalities]

    return modalities


def add_name(data: dict, type: str) -> dict:
    """Add a name field if it's missing, keep track of counts in a global
    variable."""

    if "name" not in data or not data["name"]:
        global counts  # noqa: F824
        if type not in counts:
            counts[type] = 0
        counts[type] += 1
        name = f"{type} {counts[type]}"
        data["name"] = name

    return data


ORG_MAP = {
    "LiveCanvas Technologies": Organization.LIFECANVAS,
}


def repair_organization(data: str) -> dict:
    """Convert organizations passed as strings to Organization objects."""
    organization = Organization.from_name(data)
    if organization:
        return organization.model_dump()

    organization = Organization.from_abbreviation(data)
    if organization:
        return organization.model_dump()
    else:
        if data in ORG_MAP.keys():
            return ORG_MAP[data].model_dump()
        else:
            raise ValueError(f"Unsupported organization name: {data}.")


def repair_manufacturer(data: dict) -> dict:
    """Repair the manufacturer field to ensure it's an Organization object."""

    if "manufacturer" not in data:
        return data

    if isinstance(data["manufacturer"], str):
        # Convert string to Organization object
        data["manufacturer"] = repair_organization(data["manufacturer"])

    if isinstance(data["manufacturer"], dict):
        if data["manufacturer"]["name"] == "Other" and not data["notes"]:
            data["notes"] = (
                data["notes"]
                if data["notes"]
                else "" + " (v1v2 upgrade): 'manufacturer' was set to 'Other'"
                " and notes were empty, manufacturer is unknown."
            )

    if not data["manufacturer"]:
        data["manufacturer"] = Organization.OTHER.model_dump()
        if "notes" in data:
            data["notes"] = (
                data["notes"]
                if data["notes"]
                else "" + " (v1v2 upgrade): 'manufacturer' field was missing, defaulting to 'Other'."
            )

    # Rebuild the manufacturer
    data["manufacturer"] = Organization.from_name(data["manufacturer"]["name"]).model_dump()

    return data


def upgrade_device(data: dict) -> dict:
    """Remove old Device fields"""

    remove(data, "path_to_cad")
    remove(data, "port_index")

    if "device_type" in data:
        del data["device_type"]

    if "daq_channel" in data:
        if data["daq_channel"]:
            raise ValueError("DAQ Channel has a value -- cannot upgrade record.")
        del data["daq_channel"]

    return data


def basic_device_checks(data: dict, type: str) -> dict:
    """Perform basic checks:

    - Check that name is set correctly or set to a default
    - Check that organization is not a string, but an Organization object
    """
    data = upgrade_device(data)
    data = add_name(data, type)
    data = repair_manufacturer(data)

    return data


def upgrade_generic_device(data: dict) -> dict:
    """Upgrade a generic Device object"""

    # Some Devices have a device_type field, which now specifies a real object type
    device_type = data.get("device_type", "").lower()

    data = basic_device_checks(data, "Device")

    if device_type == "computer":
        return Computer(**data).model_dump()

    return Device(**data).model_dump()


def capitalize(data: dict, field: str) -> dict:
    """Capitalize the first letter of a field in the data dictionary."""

    if field in data and isinstance(data[field], str):
        data[field] = data[field].capitalize()

    return data


def remove(data: dict, field: str):
    """Remove a field from the data dictionary if it exists."""

    if field in data:
        del data[field]


def upgrade_software(data: dict | str) -> dict:
    """Upgrade software class from v1.x to v2.0"""

    if isinstance(data, str):
        return Software(
            name=data,
        ).model_dump()
    elif isinstance(data, dict):
        remove(data, "url")
        remove(data, "parameters")

        return data
    else:
        print(data)
        raise ValueError("Software data must be a string or a dictionary.")


def build_connection_from_channel(channel: dict, device_name: str) -> Connection:
    """Build a connection object from a DAQ channel."""
    if "device_name" in channel and channel["device_name"]:
        channel_type = channel.get("channel_type", "")

        if "Output" in channel_type:
            # For output channels, DAQ sends to the device
            connection = Connection(
                source_device=device_name,
                target_device=channel["device_name"],
                source_port=channel["channel_name"],
            )
        elif "Input" in channel_type:
            # For input channels, device sends to DAQ
            connection = Connection(
                source_device=channel["device_name"],
                target_device=device_name,
                target_port=channel["channel_name"],
            )
        else:
            print(channel)
            raise ValueError(f"Unsupported channel type: {channel_type}. Expected 'Input' or 'Output'.")

        return connection

    raise ValueError("Channel must have a 'device_name' field to build a connection.")


FILTER_WAVELENGTH_MAP = {
    "493/574": [493, 574],
    "ZET405/488/561/640mv2": [405, 488, 561, 640],
    "ZET488/561m": [488, 561],
}


def upgrade_filter_helper(data: dict) -> dict:
    """Helper for the filter upgrader"""

    # Remove old Device fields
    remove(data, "device_type")
    remove(data, "filter_wheel_index")
    remove(data, "diameter")
    remove(data, "diameter_unit")
    remove(data, "thickness")
    remove(data, "thickness_unit")
    remove(data, "cut_off_frequency")
    remove(data, "cut_off_frequency_unit")
    remove(data, "cut_on_frequency")
    remove(data, "cut_on_frequency_unit")
    remove(data, "description")
    remove(data, "height")
    remove(data, "width")
    remove(data, "size_unit")
    remove(data, "wavelength_unit")

    return data


def upgrade_filter_multiband(data: dict) -> dict:
    """Handle multiband filter center wavelength issues"""
    if "center_wavelength" in data and not isinstance(data["center_wavelength"], list):
        if not data["center_wavelength"]:
            if "IR (UV/VIS Cut) M35.5 x 0.50 High Performance Machine Vision Filter" in data["name"]:
                # Special case
                data["center_wavelength"] = [285, 925]
            # Uh oh... we need to figure out what the wavelengths should be
            elif any(key in data["notes"] for key in FILTER_WAVELENGTH_MAP.keys()):
                # If the notes contain a known wavelength, use that
                for key, wavelengths in FILTER_WAVELENGTH_MAP.items():
                    if key in data["notes"]:
                        data["center_wavelength"] = wavelengths
                        break
            elif any(key in data["model"] for key in FILTER_WAVELENGTH_MAP.keys()):
                # If the model contains a known wavelength, use that
                for key, wavelengths in FILTER_WAVELENGTH_MAP.items():
                    if key in data["model"]:
                        data["center_wavelength"] = wavelengths
                        break
            else:
                print(data)
                print(data["center_wavelength"])
                raise ValueError("Multiband filter has no center_wavelength set, cannot upgrade.")
        else:
            data["center_wavelength"] = [data["center_wavelength"]]

    return data


def upgrade_filter(data: dict) -> dict:
    """Upgrade filter data to the new model."""

    data = basic_device_checks(data, "Filter")

    data = upgrade_filter_helper(data)

    # Ensure filter_type is set
    if "type" in data:
        data["filter_type"] = data["type"]
        remove(data, "type")

    # For multiband filter, make the center_wavelength a list
    if data["filter_type"] == "Multiband":
        data = upgrade_filter_multiband(data)

    filter_device = Filter(**data)
    return filter_device.model_dump()


def upgrade_positioned_device(data: dict, relative_position_list: list = []) -> dict:
    """Take v1 RelativePosition object

    and convert to the new relative_position/coordinate_system/transform pattern
    """

    relative_position = data.get("position", {})
    remove(data, "position")

    if not relative_position:
        # No information about relative position, set defaults
        data["relative_position"] = relative_position_list
        data["coordinate_system"] = None
        data["transform"] = None
    else:
        transforms = relative_position.get("device_position_transforms", [])

        data["transform"] = []

        translation = None

        for transform in transforms:
            if transform["type"] == "rotation":
                # rotation data is originally stored as a flat list 3 x 3, we convert to list of lists
                data["transform"].append(
                    Affine(
                        affine_transform=[
                            transform["rotation"][0:3],
                            transform["rotation"][3:6],
                            transform["rotation"][6:9],
                        ]
                    ).model_dump()
                )
            elif transform["type"] == "translation":
                translation = Translation(translation=transform["translation"])
                data["transform"].append(translation.model_dump())
            else:
                raise ValueError(f"Unsupported transform type: {transform['type']}")

        origin = relative_position.get("device_origin", {})
        # axes = relative_position.get("device_axes", [])

        # We can't easily recover the relative position, leave this for a data migration later
        data["relative_position"] = []

        # Rather than parse the origin/axes, we'll use a library coordinate system
        if origin == "Center of Screen on Face":
            data["coordinate_system"] = CoordinateSystemLibrary.SIPE_MONITOR_RTF
        elif "Located on face of the lens mounting surface in its center" in origin:
            data["coordinate_system"] = CoordinateSystemLibrary.SIPE_CAMERA_RBF
        elif "Located on the face of the lens mounting surface at its center" in origin:
            data["coordinate_system"] = CoordinateSystemLibrary.SIPE_CAMERA_RBF
        elif "Located at the center of the screen" in origin:
            data["coordinate_system"] = CoordinateSystemLibrary.SIPE_MONITOR_RTF
        elif (
            "Located on the front mounting flange face. Right and left conventions are relative to "
            "the front side of the speaker, ie. from the subject's perspective" in origin
        ):
            data["coordinate_system"] = CoordinateSystemLibrary.SIPE_SPEAKER_LTF
        else:
            print(relative_position)
            raise ValueError(f"Unsupported origin: {origin}")
    return data


def upgrade_enclosure(data: dict) -> dict:
    """Upgrade enclosure data to the new model."""

    data = basic_device_checks(data, "Enclosure")

    if "height" in data["size"]:
        width = data["size"].get("width", 0)
        length = data["size"].get("length", 0)
        height = data["size"].get("height", 0)
        data["size_unit"] = data["size"].get("unit", "mm")
        data["size"] = Scale(
            scale=[
                width,
                length,
                height,
            ],
        )
        data["notes"] = data["notes"] if data["notes"] else "" + " (v1v2 upgrade): Scale is width/length/height"

    enclosure = Enclosure(
        **data,
    )

    return enclosure.model_dump()


def upgrade_lens(data: dict) -> dict:
    """Upgrade lens data to the new model."""

    data = basic_device_checks(data, "Lens")

    # Remove old Device fields and deprecated fields
    remove(data, "size")  # maps to more specific fields
    remove(data, "optimized_wavelength_range")
    remove(data, "wavelength_unit")
    remove(data, "focal_length")
    remove(data, "focal_length_unit")
    remove(data, "lens_size_unit")
    remove(data, "max_aperture")

    lens = Lens(**data)
    return lens.model_dump()


COUPLING_MAPPING = {
    "SMF": "Single-mode fiber",
}


def upgrade_light_source(data: dict) -> dict:
    """Upgrade light source data to the new model."""
    # Handle the device_type field to determine which specific light source type
    device_type = data.get("device_type", "").lower()

    data = basic_device_checks(data, "Light Source")

    remove(data, "max_power")
    remove(data, "maximum_power")
    remove(data, "power_unit")
    remove(data, "item_number")

    if "coupling" in data:
        # Convert coupling to a more readable format
        data["coupling"] = COUPLING_MAPPING.get(data["coupling"], data["coupling"])

    # Old light sources have a 'type' field, which we will remove
    if "type" in data and not device_type:
        device_type = data["type"].lower()
    remove(data, "type")

    # Some light sources have a lightsource_type field, which we will remove
    if "lightsource_type" in data and not device_type:
        device_type = data["lightsource_type"].lower()
    remove(data, "lightsource_type")

    # Remove calibration date
    remove(data, "calibration_date")

    # Based on device_type, create the appropriate light source
    if (
        "laser" in device_type
        or ("notes" in data and data["notes"] and "laser" in data["notes"].lower())
        or ("name" in data and data["name"] and "laser" in data["name"].lower())
    ):
        light_source = Laser(**data)
    elif "lamp" in device_type or "wavelength_min" in data:
        light_source = Lamp(**data)
    elif "led" in device_type or "light emitting diode" in device_type or "led" in data["name"].lower():
        light_source = LightEmittingDiode(**data)
    elif "Axon 920-2 TPC" in data.get("name", ""):
        light_source = Laser(**data)
    else:
        print(data)
        raise ValueError(f"Unsupported light source type: {device_type}")

    return light_source.model_dump()


def upgrade_objective(data: dict) -> dict:
    """Upgrade objective data to the new model."""

    data = basic_device_checks(data, "Objective")

    objective = Objective(
        **data,
    )

    return objective.model_dump()


def repair_unit(broken_unit: str) -> str:
    """Check for broken unit strings and repair them"""
    if broken_unit == "nm":
        return SizeUnit.NM.value
    elif broken_unit == "um":
        return SizeUnit.UM.value
    elif broken_unit == "mm":
        return SizeUnit.MM.value
    elif broken_unit == "cm":
        return SizeUnit.CM.value
    elif broken_unit == "m":
        return SizeUnit.M.value
    else:
        return broken_unit


def _upgrade_volume_calibration_basic(data: dict) -> Optional[VolumeCalibration]:
    """Handle basic water calibration format."""

    repeats = None
    if (
        data.get("input")
        and data["input"].get("measurements")
        and len(data["input"]["measurements"]) > 0
        and data["input"]["measurements"][0].get("repeat_count")
    ):
        repeats = data["input"]["measurements"][0]["repeat_count"]

    if "valve open time (s):" in data["input"]:
        input = data["input"].get("valve open time (s):", [])
    elif "valve open time (s)" in data["input"]:
        input = data["input"].get("valve open time (s)", [])
    else:
        print(data)
        raise ValueError("Input data does not contain 'valve open time (s):' or 'valve open time (s)'.")

    if "water volume (ul):" in data["output"]:
        output = data["output"].get("water volume (ul):", [])
    elif "water volume (ul)" in data["output"]:
        output = data["output"].get("water volume (ul)", [])
    else:
        print(data)
        raise ValueError("Output data does not contain 'water volume (ul):' or 'water volume (ul)'.")

    return VolumeCalibration(
        calibration_date=data["calibration_date"],
        device_name=data["device_name"],
        repeats=repeats,
        input=input,
        input_unit=TimeUnit.S,
        output=output,
        output_unit=VolumeUnit.UL,
        notes=(
            data["notes"] if data["notes"] else "" + " (v1v2 upgrade): Liquid calibration upgraded from v1.x format."
        ),
    )


def _upgrade_volume_calibration_delivery_system(data: dict) -> Optional[VolumeCalibration]:
    """Handle water valve delivery system calibration format."""
    measurements = data.get("input", {}).get("measurements", [])

    if not measurements:
        return None

    # Extract input (valve open times) and output (water weights) from measurements
    input_values = []
    output_values = []

    for measurement in measurements:
        input_values.append(measurement.get("valve_open_time", 0))
        # Average the water weights if multiple values exist
        water_weights = measurement.get("water_weight", [])
        if water_weights:
            output_values.append(sum(water_weights) / len(water_weights))
        else:
            output_values.append(0)

    # Drop empty calibrations
    if not any(input_values) and not any(output_values):
        return None

    return VolumeCalibration(
        calibration_date=data["calibration_date"],
        device_name=data["device_name"],
        input=input_values,
        input_unit=TimeUnit.S,
        output=output_values,
        output_unit=VolumeUnit.ML,
    )


def _upgrade_volume_calibration_spot_check(data: dict) -> Optional[VolumeCalibration]:
    """Handle spot check water calibration format."""
    # Extract input and output values (could be lists or single values)
    input_values = data["input"]["valve open time (s):"]
    output_values = data["output"]["water volume (ul):"]

    # Drop empty calibrations
    if not input_values and not output_values:
        return None

    return VolumeCalibration(
        calibration_date=data["calibration_date"],
        device_name=data["device_name"],
        input=input_values,
        input_unit=TimeUnit.S,
        output=output_values,
        output_unit=VolumeUnit.UL,
    )


def _upgrade_volume_calibration(data: dict) -> Optional[dict]:
    """Upgrade volume/water calibration data."""
    description = data.get("description", "")
    input_data = data.get("input", {})
    output_data = data.get("output", {})

    # Check for different volume calibration formats
    if "Water calibration" in description:
        calibration = _upgrade_volume_calibration_basic(data)
    elif "Calibration of the water valve delivery system" in description:
        calibration = _upgrade_volume_calibration_delivery_system(data)
    elif "Spot check of water calibration" in description or (
        "valve open time (s):" in input_data and "water volume (ul):" in output_data
    ):
        calibration = _upgrade_volume_calibration_spot_check(data)
    else:
        return None

    return calibration.model_dump() if calibration else None


def _upgrade_power_calibration_basic_laser(data: dict) -> Optional[PowerCalibration]:
    """Handle basic laser power calibration with power_setting/power_output format."""
    power_setting = data["input"].get("power_setting", None)
    power_output = data["output"].get("power_output", None)

    return PowerCalibration(
        calibration_date=data["calibration_date"],
        device_name=data["device_name"],
        input=power_setting,
        input_unit=PowerUnit.PERCENT,
        output=power_output,
        output_unit=PowerUnit.MW,
    )


def _upgrade_power_calibration_measurement_laser(data: dict) -> Optional[PowerCalibration]:
    """Handle laser power calibration with power_setting/power_measurement format."""
    power_setting = data["input"].get("power_setting", {}).get("value", None)
    input_unit = data["input"].get("power_setting", {}).get("unit", PowerUnit.PERCENT.value)
    power_output = data["output"].get("power_measurement", {}).get("value", None)
    output_unit = data["output"].get("power_measurement", {}).get("unit", PowerUnit.MW.value)

    return PowerCalibration(
        calibration_date=data["calibration_date"],
        device_name=data["device_name"],
        input=[power_setting],
        input_unit=input_unit,
        output=[power_output],
        output_unit=output_unit,
    )


def _upgrade_power_calibration_percent_laser(data: dict) -> Optional[PowerCalibration]:
    """Handle laser power calibration with power percent format."""

    return PowerCalibration(
        calibration_date=data["calibration_date"],
        device_name=data["device_name"],
        input=data["input"]["power percent"],
        input_unit=PowerUnit.PERCENT,
        output=data["output"]["power mW"],
        output_unit=PowerUnit.MW,
    )


def _upgrade_power_calibration_led(data: dict) -> Optional[PowerCalibration]:
    """Handle LED power calibration format."""

    return PowerCalibration(
        calibration_date=data["calibration_date"],
        device_name=data["device_name"],
        input=data["input"]["Power setting"],
        input_unit=PowerUnit.PERCENT,
        output=data["output"]["Power mW"],
        output_unit=PowerUnit.MW,
    )


def _upgrade_power_calibration(data: dict) -> Optional[dict]:
    """Upgrade power calibration data (laser, LED)."""
    description = data.get("description", "").lower()
    input_data = data.get("input", {})
    output_data = data.get("output", {})

    # Check for different power calibration formats
    if "laser power calibration" in description and "power_setting" in input_data and "power_output" in output_data:
        calibration = _upgrade_power_calibration_basic_laser(data)
    elif (
        "laser power calibration" in description
        and "power_setting" in input_data
        and "power_measurement" in output_data
    ):
        calibration = _upgrade_power_calibration_measurement_laser(data)
    elif "laser power calibration" in description and "power percent" in input_data:
        calibration = _upgrade_power_calibration_percent_laser(data)
    elif "led calibration" in description:
        calibration = _upgrade_power_calibration_led(data)
    else:
        return None

    return calibration.model_dump() if calibration else None


def _upgrade_generic_calibration_voltage_power(data: dict) -> Optional[Calibration]:
    """Handle voltage to power calibrations (laser and optogenetic)."""
    description = data.get("description", "")
    input_data = data.get("input", {})

    if "laser power calibration" in description.lower() and "voltage (V)" in input_data:
        # Laser power calibration with voltage input
        return Calibration(
            calibration_date=data["calibration_date"],
            description=data.get("description", ""),
            device_name=data["device_name"],
            input=data["input"]["voltage (V)"],
            input_unit=VoltageUnit.V,
            output=data["output"]["power (mW)"],
            output_unit=PowerUnit.MW,
        )
    elif "Optogenetic calibration" in description:
        # Optogenetic calibration with input voltage and laser power output
        input_voltages = data["input"]["input voltage (v)"]
        output_powers = data["output"]["laser power (mw)"]

        # Filter out 'NA' values from output
        filtered_inputs = []
        filtered_outputs = []
        for i, output in enumerate(output_powers):
            if output != "NA":
                filtered_inputs.append(input_voltages[i])
                filtered_outputs.append(output)

        # Drop empty calibrations
        if not filtered_inputs and not filtered_outputs:
            return None

        return Calibration(
            calibration_date=data["calibration_date"],
            description=data.get("description", ""),
            device_name=data["device_name"],
            input=filtered_inputs,
            input_unit=VoltageUnit.V,
            output=filtered_outputs,
            output_unit=PowerUnit.MW,
            notes=(
                data["notes"]
                if data["notes"]
                else "" + " (v1v2 upgrade): Optogenetic calibration upgraded from v1.x format. NA values filtered out."
            ),
        )

    return None


def _upgrade_generic_calibration(data: dict) -> Optional[dict]:
    """Upgrade generic calibration data that doesn't fit volume or power categories."""
    calibration = _upgrade_generic_calibration_voltage_power(data)

    if calibration:
        return calibration.model_dump()

    return None


IGNORED_CALIBRATIONS = [
    "solenoid open time (ms) = slope * expected water volume (mL) + intercept",
]


def upgrade_calibration(data: dict) -> Optional[dict]:
    """Upgrade calibration information by categorizing and delegating to specific handlers."""

    if any(ignored in data.get("description", "") for ignored in IGNORED_CALIBRATIONS):
        # Skip ignored calibrations
        return None

    # Try volume calibrations first
    result = _upgrade_volume_calibration(data)
    if result:
        return result

    # Try power calibrations
    result = _upgrade_power_calibration(data)
    if result:
        return result

    # Try sound intensity calibrations
    result = _upgrade_sound_calibration(data)
    if result:
        return result

    # Try generic calibrations
    result = _upgrade_generic_calibration(data)
    if result:
        return result

    # If none of the handlers can process it, raise an error
    raise ValueError(f"Unsupported calibration: {data}")


CCF_MAPPING = {
    "ALM": CCFv3.MO,
    "Primary Motor Cortex": CCFv3.MO,
    "striatum": CCFv3.CP,
    "Striatum": CCFv3.CP,
    "Striatum and GPe": CCFv3.GPE,
    "Striatum and Gpe": CCFv3.GPE,
    "Gpe and Striatum": CCFv3.GPE,
    "PPN and MRN": CCFv3.MRN,
    "V1 center": CCFv3.VISP,
    "GenFacCran": CCFv3.GVIIN,
}


def upgrade_targeted_structure(data: dict | str) -> dict:
    """Upgrade targeted structure, especially convert strings to structure objects"""

    if isinstance(data, str):
        data = data.strip()
        if hasattr(CCFv3, data.upper()):
            return getattr(CCFv3, data.upper()).model_dump()
        if "none" in data.lower():
            return CCFv3.ROOT.model_dump()
        if data in CCF_MAPPING.keys():
            return CCF_MAPPING[data].model_dump()
        else:
            raise ValueError(f"Unsupported targeted structure: {data}. " "Expected one of the CCF structures.")

    return data


def upgrade_registry(data: dict) -> dict:
    """Input dictionary is anything that has a "registry" field

    Output replaces the registry object dictionary with just a Registry enum object
    """

    if "registry" in data and data["registry"]:
        data["registry"] = getattr(Registry, data["registry"]["abbreviation"].upper())

    return data


def upgrade_reagent(data: dict) -> dict:
    """Upgrade reagents from V1 to V2"""
    upgraded_data = data.copy()

    if "source" in upgraded_data and upgraded_data["source"]:
        if upgraded_data["source"]:
            if isinstance(upgraded_data["source"], str):
                # Convert source to organization
                upgraded_data["source"] = repair_organization(upgraded_data["source"])
            else:
                upgraded_data["source"] = upgrade_registry(upgraded_data["source"])
    else:
        # Unknown source
        upgraded_data["source"] = Organization.OTHER

    if "rrid" in upgraded_data and upgraded_data["rrid"]:
        upgraded_data["rrid"] = upgrade_registry(upgraded_data["rrid"])

    return Reagent(**upgraded_data).model_dump()


def _upgrade_sound_calibration(data: dict) -> Optional[dict]:
    """Handle sound calibration with equation parameters in input field."""
    description = data.get("description", "")
    input_data = data.get("input", {})

    # Check if this is a sound calibration with equation parameters
    if ("sound_volume" in description.lower() or "sound" in description.lower()) and isinstance(input_data, dict):
        # Extract equation parameters with well-named keys
        equation_parameters = {}
        for param_name, param_value in input_data.items():
            if param_name in ["a", "b", "c"]:
                equation_parameters[f"equation_parameter_{param_name}"] = param_value
            else:
                equation_parameters[param_name] = param_value

        # Create the calibration fit
        calibration_fit = CalibrationFit(fit_type=FitType.OTHER, fit_parameters=equation_parameters)

        return Calibration(
            calibration_date=data["calibration_date"],
            description=data.get("description", ""),
            device_name=data["device_name"],
            input=[],  # No input measurements, equation parameters are in fit
            input_unit=SoundIntensityUnit.DB,  # Placeholder unit since no actual input
            output=[],  # No output measurements
            output_unit=SoundIntensityUnit.DB,  # Placeholder unit since no actual output
            fit=calibration_fit,
            notes=data.get("notes", "")
            + (
                " (v1v2 upgrade): Sound calibration equation upgraded from v1.x format, equation volume = "
                "log(1 - ((dB - c) / a)) / b."
            ),
        ).model_dump()

    return None
