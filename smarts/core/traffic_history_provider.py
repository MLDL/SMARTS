import json
import math
import random
from itertools import cycle
from typing import Set, Dict

import numpy as np

from .controllers import ActionSpaceType
from .coordinates import BoundingBox, Pose, Heading
from .provider import ProviderState
from .scenario import Mission, EndlessGoal, Start
from .vehicle import VEHICLE_CONFIGS, VehicleState


class TrafficHistoryProvider:
    def __init__(self):
        self._is_setup = False
        self._current_traffic_history = None
        self.replaced_vehicle_ids = set()

    def setup(self, scenario) -> ProviderState:
        self._is_setup = True
        self._traffic_histories = scenario.discover_traffic_histories() or [{}]
        self._current_traffic_history = next(self.histories)
        return ProviderState()

    @property
    def histories(self):
        for history in cycle(self._traffic_histories):
            yield history

    def set_replaced_ids(self, vehicle_ids: list):
        self.replaced_vehicle_ids.update(vehicle_ids)

    def reset(self):
        self._current_traffic_history = next(self.histories)

    def teardown(self):
        self._is_setup = False
        self._frame = None
        self._current_traffic_history = None
        self._traffic_histories = None
        self.replaced_vehicle_ids = set()

    @property
    def action_spaces(self) -> Set[ActionSpaceType]:
        return {ActionSpaceType.TargetPose}

    def sync(self, provider_state):
        # Ignore other sim state
        pass

    def step(self, provider_actions, dt, elapsed_sim_time) -> ProviderState:
        timestamp = min(
            (
                float(ts)
                for ts in self._current_traffic_history
                if float(ts) >= elapsed_sim_time
            ),
            default=None,
        )
        if (
            not self._current_traffic_history
            or timestamp is None
            or str(timestamp) not in self._current_traffic_history
        ):
            return ProviderState(vehicles=[], traffic_light_systems=[])

        vehicle_type = "passenger"
        states = ProviderState(
            vehicles=[
                VehicleState(
                    vehicle_id=v_id,
                    vehicle_type=vehicle_type,
                    pose=Pose.from_center(
                        [*vehicle_state["position"][:2], 0,],
                        Heading(vehicle_state["heading"]),
                    ),
                    # TODO: specify dimensions
                    dimensions=VEHICLE_CONFIGS[vehicle_type].dimensions,
                    speed=vehicle_state["speed"],
                    source="HISTORY",
                )
                for v_id, vehicle_state in self._current_traffic_history[
                    str(timestamp)
                ].items()
                if v_id not in self.replaced_vehicle_ids
            ],
            traffic_light_systems=[],
        )
        return states

    def create_vehicle(self, provider_vehicle: VehicleState):
        pass
