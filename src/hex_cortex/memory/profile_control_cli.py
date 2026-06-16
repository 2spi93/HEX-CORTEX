"""Short alias for the profile operator control entrypoint."""


def main(argv: list[str] | None = None) -> int:
    from hex_cortex.memory.profile_operator_control_cli import main as control_main

    return control_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
