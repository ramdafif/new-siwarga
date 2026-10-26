from importlib import metadata
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent


def closure(requirements):
    pending = [Requirement(value) for value in requirements]
    selected = {}
    visited = set()
    environments = []
    for platform, system in (("win32", "Windows"), ("linux", "Linux")):
        environment = default_environment()
        environment.update(sys_platform=platform, platform_system=system)
        environments.append(environment)
    while pending:
        requirement = pending.pop()
        identity = canonicalize_name(requirement.name)
        signature = (identity, tuple(sorted(requirement.extras)))
        if signature in visited:
            continue
        visited.add(signature)
        distribution = metadata.distribution(requirement.name)
        selected[identity] = f"{distribution.metadata['Name']}=={distribution.version}"
        for dependency in distribution.requires or []:
            needed = Requirement(dependency)
            extras = requirement.extras or {""}
            if needed.marker is None or any(needed.marker.evaluate(dict(environment, extra=extra))
                                             for environment in environments for extra in extras):
                pending.append(needed)
    return selected


def lines(name):
    return [line.strip() for line in (ROOT / name).read_text().splitlines()
            if line.strip() and not line.startswith(("-", "#"))]


def main():
    runtime = closure(lines("requirements.txt"))
    development = closure(lines("requirements.txt") + lines("requirements-dev.txt"))
    (ROOT / "requirements.lock").write_text("\n".join(runtime[name] for name in sorted(runtime)) + "\n", encoding="ascii")
    (ROOT / "requirements-dev.lock").write_text("-r requirements.lock\n" +
        "\n".join(development[name] for name in sorted(development) if name not in runtime) + "\n", encoding="ascii")
    print(f"Locked {len(runtime)} runtime and {len(development) - len(runtime)} development dependencies.")


if __name__ == "__main__":
    main()
