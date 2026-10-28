"""E49 function-only copy. Load with explicit E-only bindings; no top-level side effects."""

def maven_generation_options(profile=LEGACY):
    """Legacy argv stays byte-for-byte equivalent; only reviewer-required flags vary."""
    common = ['-Duse_separate_classloader=false', '-Dtest_archive=false', '-Dcriterion=BRANCH']
    if profile == LEGACY:
        return common + ['-Dassertions=false', '-Dno_runtime_dependency=true', '-Dtest_scaffolding=false', '-Dsearch_budget=60']
    if profile == REVIEWER:
        return common + ['-Dassertions=true', '-Dno_runtime_dependency=false', '-Dtest_scaffolding=true', '-Dsearch_budget=60', '-Dassertion_strategy=MUTATION']
    raise ValueError(f'Unknown EvoSuite generation profile: {profile}')
