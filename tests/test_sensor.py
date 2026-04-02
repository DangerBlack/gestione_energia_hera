"""Unit tests for sensor.py — all mocked, no real credentials needed."""
import sys
from unittest.mock import MagicMock

import pytest

import enum
from sys import modules as _sys_modules

# Grab the enum classes registered in conftest for assertions
_SensorDeviceClass = _sys_modules['homeassistant.components.sensor'].SensorDeviceClass
_SensorStateClass  = _sys_modules['homeassistant.components.sensor'].SensorStateClass

from gruppo_hera.sensor import _latest_bill, SENSOR_DESCRIPTIONS, GruppoHeraSensor


# ---------------------------------------------------------------------------
# _latest_bill
# ---------------------------------------------------------------------------

def test_latest_bill_sorted_by_date():
    bills = [
        {'id': 'jan', 'amount': 50.0, 'date': '2024-01-01'},
        {'id': 'mar', 'amount': 150.0, 'date': '2024-03-01'},
        {'id': 'feb', 'amount': 100.0, 'date': '2024-02-01'},
    ]
    assert _latest_bill(bills)['id'] == 'mar'


def test_latest_bill_sorted_by_issue_date():
    bills = [
        {'id': 'old', 'amount': 50.0, 'issueDate': '2023-12-01'},
        {'id': 'new', 'amount': 100.0, 'issueDate': '2024-06-01'},
    ]
    assert _latest_bill(bills)['id'] == 'new'


def test_latest_bill_fallback_to_first_when_no_date():
    bills = [
        {'id': 'first', 'amount': 50.0},
        {'id': 'second', 'amount': 100.0},
    ]
    assert _latest_bill(bills)['id'] == 'first'


def test_latest_bill_single_entry():
    bills = [{'id': 'only', 'amount': 75.0}]
    assert _latest_bill(bills)['id'] == 'only'


def test_latest_bill_date_takes_priority_over_issue_date():
    """'date' field has higher priority than 'issueDate' per _BILL_DATE_FIELDS order."""
    bills = [
        {'id': 'b1', 'date': '2024-06-01', 'issueDate': '2023-01-01'},
        {'id': 'b2', 'date': '2024-01-01', 'issueDate': '2025-01-01'},
    ]
    assert _latest_bill(bills)['id'] == 'b1'


# ---------------------------------------------------------------------------
# SENSOR_DESCRIPTIONS
# ---------------------------------------------------------------------------

def test_sensor_descriptions_unique_keys():
    keys = [d.key for d in SENSOR_DESCRIPTIONS]
    assert len(keys) == len(set(keys)), "Duplicate sensor description keys found"


def test_energy_sensors_have_kwh_unit():
    energy_sensors = [d for d in SENSOR_DESCRIPTIONS if d.key != 'last_bill_amount']
    for desc in energy_sensors:
        assert desc.native_unit_of_measurement == 'kWh', f"{desc.key} should use kWh"


def test_bill_sensor_uses_eur():
    bill = next(d for d in SENSOR_DESCRIPTIONS if d.key == 'last_bill_amount')
    assert bill.native_unit_of_measurement == 'EUR'


def test_average_daily_uses_measurement_state_class():
    avg = next(d for d in SENSOR_DESCRIPTIONS if d.key == 'average_daily')
    assert avg.state_class == _SensorStateClass.MEASUREMENT


def test_consumption_sensors_use_total_increasing():
    consumption_keys = {'total_consumption', 'consumption_f0', 'consumption_f1',
                        'consumption_f2', 'consumption_f3'}
    for desc in SENSOR_DESCRIPTIONS:
        if desc.key in consumption_keys:
            assert desc.state_class == _SensorStateClass.TOTAL_INCREASING, (
                f"{desc.key} should be TOTAL_INCREASING"
            )


# ---------------------------------------------------------------------------
# GruppoHeraSensor.native_value
# ---------------------------------------------------------------------------

def _make_coordinator(data: dict) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = True
    return coordinator


def _make_sensor(coordinator, description_key: str, contract_id=None,
                 service_type='ELECTRIC', band=None) -> GruppoHeraSensor:
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == description_key)
    return GruppoHeraSensor(coordinator, desc, contract_id, service_type, 'Via Test', 0, band)


def test_native_value_total_consumption():
    data = {
        'usage': {'c1': {'list': [{'totalUsage': 300.0, 'averageUsage': 10.0, 'reads': []}]}},
        'bills': [],
        'contracts': [],
    }
    sensor = _make_sensor(_make_coordinator(data), 'total_consumption', contract_id='c1')
    assert sensor.native_value == 300.0


def test_native_value_band_f1():
    data = {
        'usage': {'c1': {'list': [{'totalUsage': 300.0, 'averageUsage': 10.0, 'reads': [
            {'type': 'F1', 'value': 180.0},
            {'type': 'F2', 'value': 120.0},
        ]}]}},
        'bills': [],
        'contracts': [],
    }
    sensor = _make_sensor(_make_coordinator(data), 'consumption_f1', contract_id='c1', band='F1')
    assert sensor.native_value == 180.0


def test_native_value_average_daily():
    data = {
        'usage': {'c1': {'list': [{'totalUsage': 300.0, 'averageUsage': 9.7, 'reads': []}]}},
        'bills': [],
        'contracts': [],
    }
    sensor = _make_sensor(_make_coordinator(data), 'average_daily', contract_id='c1')
    assert sensor.native_value == 9.7


def test_native_value_last_bill_amount():
    data = {
        'usage': {},
        'contracts': [],
        'bills': [
            {'id': 'b1', 'amount': 85.0, 'date': '2024-01-01'},
            {'id': 'b2', 'amount': 110.0, 'date': '2024-06-01'},
        ],
    }
    sensor = _make_sensor(_make_coordinator(data), 'last_bill_amount')
    assert sensor.native_value == 110.0


def test_native_value_returns_zero_when_no_usage():
    data = {'usage': {}, 'bills': [], 'contracts': []}
    sensor = _make_sensor(_make_coordinator(data), 'total_consumption', contract_id='c1')
    assert sensor.native_value == 0


def test_sensor_available_reflects_coordinator():
    coordinator = _make_coordinator({'usage': {}, 'bills': [], 'contracts': []})
    coordinator.last_update_success = False
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == 'total_consumption')
    sensor = GruppoHeraSensor(coordinator, desc, 'c1', 'ELECTRIC', 'addr', 0)
    assert sensor.available is False
