"""Build the Space Invaders environment."""

import ale_py
import gymnasium as gym

gym.register_envs(ale_py)

ENV_ID = "ALE/SpaceInvaders-v5"


def make_env(render: bool = False) -> gym.Env:
    """Return the ALE Space Invaders environment with the v5 defaults.

    RAM observations (obs_type="ram"). The RGB screen for decode() and video
    comes from env.unwrapped.ale.getScreenRGB(), not from the observation.
    render selects the human render mode for interactive viewing; it does not
    affect decisions or scoring.
    """
    return gym.make(
        ENV_ID,
        obs_type="ram",
        frameskip=4,
        repeat_action_probability=0.25,
        full_action_space=False,
        max_num_frames_per_episode=108000,
        render_mode="human" if render else None,
    )
