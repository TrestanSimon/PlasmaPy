"""
Tests for functionality contained in
`plasmapy.analysis.swept_langmuir.floating_potential`.
"""

import numpy as np
import pytest

from unittest import mock

from plasmapy.analysis import fit_functions as ffuncs
from plasmapy.analysis import swept_langmuir as _sl
from plasmapy.analysis.swept_langmuir.floating_potential import (
    find_floating_potential,
    FloatingPotentialResults,
)
from plasmapy.utils.exceptions import PlasmaPyWarning


def test_floating_potential_namedtuple():
    """
    Test structure of the namedtuple used to return computed floating potential
    data.
    """

    assert issubclass(FloatingPotentialResults, tuple)
    assert hasattr(FloatingPotentialResults, "_fields")
    assert FloatingPotentialResults._fields == (
        "vf",
        "vf_err",
        "rsq",
        "func",
        "islands",
        "indices",
    )
    assert hasattr(FloatingPotentialResults, "_field_defaults")
    assert FloatingPotentialResults._field_defaults == {}


class TestFindFloatingPotential:
    """
    Tests for function
    `~plasmapy.analysis.swept_langmuir.floating_potential.find_floating_potential`.
    """

    _null_result = FloatingPotentialResults(
        vf=np.nan, vf_err=np.nan, rsq=None, func=None, islands=None, indices=None
    )._asdict()
    _voltage = np.linspace(-10.0, 15, 70)
    _linear_current = np.linspace(-3.1, 4.1, 70)
    _linear_p_sine_current = _linear_current + 1.2 * np.sin(1.2 * _voltage)
    _exp_current = -1.3 + 2.2 * np.exp(_voltage)

    def test_call_of_check_sweep(self):
        """
        Test `find_floating_potential` appropriately calls
        `plasmapy.analysis.swept_langmuir.helpers.check_sweep` so we can relay on
        the `check_sweep` tests.
        """
        varr = np.linspace(-20.0, 20.0, 100)
        carr = np.linspace(-20.0, 20.0, 100)

        assert _sl.helpers.check_sweep is _sl.floating_potential.check_sweep

        with mock.patch(_sl.floating_potential.__name__ + ".check_sweep") as mock_cs:
            mock_cs.return_value = varr, carr
            find_floating_potential(voltage=varr, current=carr, fit_type="linear")

            assert mock_cs.call_count == 1

            # passed args
            assert len(mock_cs.call_args[0]) == 2
            assert np.array_equal(mock_cs.call_args[0][0], varr)
            assert np.array_equal(mock_cs.call_args[0][1], carr)

            # passed kwargs
            assert mock_cs.call_args[1] == {"strip_units": True}

    @pytest.mark.parametrize(
        "kwargs, _error",
        [
            # errors on kwarg fit_type
            (
                {
                    "voltage": np.array([1.0, 2, 3, 4]),
                    "current": np.array([-1.0, 0, 1, 2]),
                    "fit_type": "wrong",
                },
                ValueError,
            ),
            #
            # errors on kwarg min_points
            (
                {
                    "voltage": np.array([1.0, 2, 3, 4]),
                    "current": np.array([-1.0, 0, 1, 2]),
                    "min_points": "wrong",
                },
                TypeError,
            ),
            (
                {
                    "voltage": np.array([1.0, 2, 3, 4]),
                    "current": np.array([-1.0, 0, 1, 2]),
                    "min_points": -1,
                },
                ValueError,
            ),
            #
            # errors on kwarg threshold
            (
                {
                    "voltage": np.array([1.0, 2, 3, 4]),
                    "current": np.array([-1.0, 0, 1, 2]),
                    "threshold": -1,
                },
                ValueError,
            ),
            (
                {
                    "voltage": np.array([1.0, 2, 3, 4]),
                    "current": np.array([-1.0, 0, 1, 2]),
                    "threshold": "wrong type",
                },
                TypeError,
            ),
            #
            # TypeError on voltage/current arrays from check_sweep
            (
                {
                    "voltage": "not an array",
                    "current": np.array([-1.0, 0, 1, 2]),
                    "fit_type": "linear",
                },
                TypeError,
            ),
            #
            # ValueError on voltage/current arrays from check_sweep
            #   (not linearly increasing)
            (
                {
                    "voltage": np.array([2.0, 1, 0, -1]),
                    "current": np.array([-1.0, 0, 1, 2]),
                    "fit_type": "linear",
                },
                ValueError,
            ),
        ],
    )
    def test_raises(self, kwargs, _error):
        """Test scenarios that raise `Exception`s."""
        with pytest.raises(_error):
            find_floating_potential(**kwargs)

    @pytest.mark.parametrize(
        "kwargs, expected, _warning",
        [
            # too many crossing islands
            (
                {
                    "voltage": _voltage,
                    "current": _linear_p_sine_current,
                    "fit_type": "linear",
                },
                {
                    **_null_result,
                    "func": ffuncs.Linear(),
                    "islands": [slice(27, 29), slice(36, 38), slice(39, 41)],
                },
                PlasmaPyWarning,
            ),
            #
            # min_points is larger than array size
            (
                {
                    "voltage": _voltage,
                    "current": _linear_p_sine_current,
                    "fit_type": "linear",
                    "threshold": 8,
                    "min_points": 80,
                },
                {
                    **_null_result,
                    "vf": 0.6355491,
                    "vf_err": 0.03306472,
                    "rsq": 0.8446441,
                    "func": ffuncs.Linear(),
                    "islands": [slice(27, 41),],
                    "indices": slice(0, 70),
                },
                PlasmaPyWarning,
            ),
        ],
    )
    def test_warnings(self, kwargs, expected, _warning):
        """Test scenarios that issue warnings."""
        with pytest.warns(_warning):
            results = find_floating_potential(**kwargs)
            assert isinstance(results, FloatingPotentialResults)

        for key, val in expected.items():
            rtn_val = getattr(results, key)

            if val is None:
                assert rtn_val is None
            elif key == "func" and val is not None:
                assert isinstance(rtn_val, val.__class__)
            elif np.isscalar(val):
                if np.isnan(val):
                    assert np.isnan(rtn_val)
                else:
                    assert np.isclose(rtn_val, val)
            else:
                assert rtn_val == val

    @pytest.mark.parametrize(
        "min_points, fit_type, islands, indices",
        [
            (0, "linear", [slice(29, 31), ], slice(0, 70)),
            (1, "linear", [slice(29, 31), ], slice(29, 31)),
            (15, "linear", [slice(29, 31), ], slice(22, 38)),
            (16, "linear", [slice(29, 31), ], slice(22, 38)),
            (0.14, "linear", [slice(29, 31), ], slice(25, 35)),
            #
            # rely on default min_points
            # - linear -> 0.1 * array size & ceiling to the nearest even
            # - exponential -> 0.2 * array size & ceiling to the nearest even
            (None, "linear", [slice(29, 31), ], slice(26, 34)),
            (None, "exponential", [slice(26, 28), ], slice(20, 34)),
        ],
    )
    def test_kwarg_min_points(self, min_points, fit_type, islands, indices):
        voltage = self._voltage
        current = self._linear_current if fit_type == "linear" else self._exp_current
        results = find_floating_potential(
            voltage, current, min_points=min_points, fit_type=fit_type,
        )
        assert isinstance(results, FloatingPotentialResults)

        assert results.islands == islands
        assert results.indices == indices
