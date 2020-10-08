import logging
import gym
import pytest

from smarts.core.controllers import ActionSpaceType
from smarts.core.agent_interface import (
    AgentInterface,
    NeighborhoodVehicles,
    DrivableAreaGridMap,
    OGM,
    RGB,
    RoadWaypoints,
)
from smarts.core.agent import AgentSpec, AgentPolicy
from smarts.core.colors import SceneColors

from panda3d.core import OrthographicLens, Point2, Point3
import numpy as np

logging.basicConfig(level=logging.INFO)

AGENT_ID = "Agent-007"

NUM_STEPS = 15
MAP_WIDTH = 1536
MAP_HEIGHT = 1536
HALF_WIDTH = MAP_WIDTH / 2
HALF_HEIGHT = MAP_HEIGHT / 2
MAP_RESOLUTION = 50 / 256
SAMPLE_RANGE = 10

ROAD_COLOR = np.array(SceneColors.Road.value[0:3]) * 255


@pytest.fixture
def agent_spec():
    return AgentSpec(
        interface=AgentInterface(
            road_waypoints=RoadWaypoints(40),
            neighborhood_vehicles=NeighborhoodVehicles(
                radius=max(MAP_WIDTH * MAP_RESOLUTION, MAP_HEIGHT * MAP_RESOLUTION)
                * 0.5
            ),
            drivable_area_grid_map=DrivableAreaGridMap(
                width=MAP_WIDTH, height=MAP_HEIGHT, resolution=MAP_RESOLUTION
            ),
            ogm=OGM(width=MAP_WIDTH, height=MAP_HEIGHT, resolution=MAP_RESOLUTION),
            rgb=RGB(width=MAP_WIDTH, height=MAP_HEIGHT, resolution=MAP_RESOLUTION),
            action=ActionSpaceType.Lane,
        ),
        policy_builder=lambda: AgentPolicy.from_function(lambda _: "keep_lane"),
    )


@pytest.fixture
def env(agent_spec):
    env = gym.make(
        "smarts.env:hiway-v0",
        scenarios=["scenarios/loop"],
        agent_specs={AGENT_ID: agent_spec},
        headless=True,
        visdom=False,
        timestep_sec=0.1,
        seed=2,
    )

    yield env
    env.close()


def project_2d(lens, img_metadata, pos):
    center = np.array(img_metadata.camera_pos)
    heading = np.radians(img_metadata.camera_heading_in_degrees)

    # Translate according to the camera center
    p_translated = pos - center

    # Apply the inverse rotation matrix to the vehicle position, same effect as rotating the camera
    p_rotated = np.array(
        [
            p_translated[0] * np.cos(-heading) - p_translated[1] * np.sin(-heading),
            p_translated[0] * np.sin(-heading) + p_translated[1] * np.cos(-heading),
            p_translated[2],
        ]
    )

    v_2d_pos_normalized = Point2()
    v_3d_pos = Point3(
        p_rotated[0], p_rotated[2], p_rotated[1]
    )  # y and z are flipped for project() in panda3D

    x = int(HALF_HEIGHT)
    y = int(HALF_WIDTH)

    # project() returns true if given 3d point is within the viewing frustum
    if lens.project(v_3d_pos, v_2d_pos_normalized):

        # v_2d_pos_normlized ranges (-1, 1) in both directions, with (-1,-1) being the lower-left corner
        # Sensor image has non-negative pixel positions, with (0, 0) starting from top-left corner
        # x and y are swapped between sensor image and the image projected from panda3D lens
        x = int(-v_2d_pos_normalized[1] * HALF_HEIGHT + HALF_HEIGHT)
        y = int(v_2d_pos_normalized[0] * HALF_WIDTH + HALF_WIDTH)

    return x, y


def sample_vehicle_pos(
    lens, rgb, next_rgb, ogm, next_ogm, drivable_area, next_drivable_area, vehicle_pos
):
    rgb_x, rgb_y = project_2d(lens, rgb.metadata, vehicle_pos)
    ogm_x, ogm_y = project_2d(lens, ogm.metadata, vehicle_pos)
    drivable_area_x, drivable_area_y = project_2d(
        lens, drivable_area.metadata, vehicle_pos
    )

    # Sometimes grid maps are one frame/step behind current positions of the vehicles
    next_rgb_x, next_rgb_y = project_2d(lens, next_rgb.metadata, vehicle_pos)
    next_ogm_x, next_ogm_y = project_2d(lens, next_ogm.metadata, vehicle_pos)
    next_drivable_area_x, next_drivable_area_y = project_2d(
        lens, next_drivable_area.metadata, vehicle_pos
    )

    # Check if vehicles are rendered at the expected position
    # RGB
    assert (
        np.count_nonzero(rgb.data[rgb_x, rgb_y, :])
        and np.count_nonzero(rgb.data[rgb_x, rgb_y, :] != ROAD_COLOR)
    ) or (
        np.count_nonzero(next_rgb.data[next_rgb_x, next_rgb_y, :])
        and np.count_nonzero(next_rgb.data[next_rgb_x, next_rgb_y, :] != ROAD_COLOR)
    )

    # OGM
    assert np.count_nonzero(ogm.data[ogm_x, ogm_y, :]) or np.count_nonzero(
        next_ogm.data[next_ogm_x, next_ogm_y, :]
    )

    # Check if vehicles are within drivable area
    # Drivable area grid map

    # Temporary debug code: log the following info to understand sporadic test failure on gitlab
    # Will be removed when failure no longer occurs
    x_min = max(drivable_area_x - SAMPLE_RANGE, 0)
    x_max = min(drivable_area_x + SAMPLE_RANGE, MAP_HEIGHT)
    y_min = max(drivable_area_y - SAMPLE_RANGE, 0)
    y_max = min(drivable_area_y + SAMPLE_RANGE, MAP_WIDTH)
    print(drivable_area_x, drivable_area_y, np.count_nonzero(drivable_area.data))
    print(drivable_area.data[x_min:x_max, drivable_area_y])
    print(drivable_area.data[drivable_area_x, y_min:y_max])

    next_x_min = max(next_drivable_area_x - SAMPLE_RANGE, 0)
    next_x_max = min(next_drivable_area_x + SAMPLE_RANGE, MAP_HEIGHT)
    next_y_min = max(next_drivable_area_y - SAMPLE_RANGE, 0)
    next_y_max = min(next_drivable_area_y + SAMPLE_RANGE, MAP_WIDTH)
    print(
        next_drivable_area_x,
        next_drivable_area_y,
        np.count_nonzero(next_drivable_area.data),
    )
    print(next_drivable_area.data[next_x_min:next_x_max, next_drivable_area_y])
    print(next_drivable_area.data[next_drivable_area_x, next_y_min:next_y_max])

    assert np.count_nonzero(
        drivable_area.data[drivable_area_x, drivable_area_y, :]
    ) or np.count_nonzero(
        next_drivable_area.data[next_drivable_area_x, next_drivable_area_y, :]
    )


def test_observations(env, agent_spec):
    agent = agent_spec.build_agent()
    observations = env.reset()

    # Let the agent step for a while
    for _ in range(NUM_STEPS):
        agent_obs = observations[AGENT_ID]
        agent_action = agent.act(agent_obs)
        observations, _, _, _ = env.step({AGENT_ID: agent_action})

    # Store observations for an additional step,
    # because sometimes grid maps are one frame/step behind current positions of the vehicles
    next_agent_obs = observations[AGENT_ID]
    next_agent_action = agent.act(next_agent_obs)
    next_observations, _, _, _ = env.step({AGENT_ID: next_agent_action})

    # RGB
    rgb = observations[AGENT_ID].top_down_rgb
    next_rgb = next_observations[AGENT_ID].top_down_rgb

    # OGM
    ogm = observations[AGENT_ID].occupancy_grid_map
    next_ogm = next_observations[AGENT_ID].occupancy_grid_map

    # Drivable area
    drivable_area = observations[AGENT_ID].drivable_area_grid_map
    next_drivable_area = next_observations[AGENT_ID].drivable_area_grid_map

    lens = OrthographicLens()
    lens.setFilmSize(MAP_RESOLUTION * MAP_WIDTH, MAP_RESOLUTION * MAP_HEIGHT)

    # Check for ego vehicle
    ego_vehicle_position = observations[AGENT_ID].ego_vehicle_state.position
    sample_vehicle_pos(
        lens,
        rgb,
        next_rgb,
        ogm,
        next_ogm,
        drivable_area,
        next_drivable_area,
        ego_vehicle_position,
    )

    # Check for neighbor vehicles
    for neighbor_vehicle in observations[AGENT_ID].neighborhood_vehicle_states:
        sample_vehicle_pos(
            lens,
            rgb,
            next_rgb,
            ogm,
            next_ogm,
            drivable_area,
            next_drivable_area,
            neighbor_vehicle.position,
        )

    # Check for roads
    for lane_wps in observations[AGENT_ID].road_waypoints.lanes.values():
        first_wp = lane_wps[0]
        last_wp = lane_wps[-1]

        first_wp_pos = np.array([first_wp.pos[0], first_wp.pos[1], 0])
        last_wp_pos = np.array([last_wp.pos[0], last_wp.pos[1], 0])

        rgb_first_wp_x, rgb_first_wp_y = project_2d(lens, rgb.metadata, first_wp_pos)
        rgb_last_wp_x, rgb_last_wp_y = project_2d(lens, rgb.metadata, last_wp_pos)

        drivable_area_first_wp_x, drivable_area_first_wp_y = project_2d(
            lens, drivable_area.metadata, first_wp_pos
        )
        drivable_area_last_wp_x, drivable_area_last_wp_y = project_2d(
            lens, drivable_area.metadata, last_wp_pos
        )

        # Check if roads are rendered at the start and end of road waypoint paths
        # RGB
        assert np.count_nonzero(rgb.data[rgb_first_wp_x, rgb_first_wp_y, :])
        assert np.count_nonzero(rgb.data[rgb_last_wp_x, rgb_last_wp_y, :])

        # Drivable Area Grid Map
        assert np.count_nonzero(
            drivable_area.data[drivable_area_first_wp_x, drivable_area_first_wp_y, :]
        )
        assert np.count_nonzero(
            drivable_area.data[drivable_area_last_wp_x, drivable_area_last_wp_y, :]
        )
