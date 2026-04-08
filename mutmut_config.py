"""Mutmut configuration — target pure-logic modules only."""


def init():
    pass


def pre_mutation(context):
    """Skip mutations in files we don't want to test."""
    # Only mutate pure-logic modules where surviving mutants are meaningful
    allowed = [
        "src/aeolus/geo.py",
        "src/aeolus/transforms.py",
        "src/aeolus/metrics/base.py",
        "src/aeolus/cache.py",
    ]
    if context.filename not in allowed:
        context.skip = True
