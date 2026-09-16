"""Offline simulator.

The simulator replaces the Discord gateway with a scripted world: fake members, fake
messages, a fake clock. It drives exactly the same engines the live bot uses, so a
scenario is both a demo you can watch and a regression test you can assert on.

    python -m botsuite.sim list
    python -m botsuite.sim raid
    python -m botsuite.sim all
"""

from .world import SimWorld

__all__ = ["SimWorld"]
