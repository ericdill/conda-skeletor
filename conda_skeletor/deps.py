
def categorize_deps(iterate_over_library_output,
                    is_build_callable=None, is_testing_dep_callable=None,
                    is_runtime_dep_callable=None):
    """(Attempt to) Categorize the deps as testing/runtime/build

    is_*_dep_callable functions get called to determine which (if any) of the
    dependencies of a module are actually testing/build/runtime deps.  These
    functions need to accept three positional arguments:
    'module_name', 'full_path_to_module' and 'module_deps'. These functions are
    expected to return a list of dependencies. If no dependencies match, return
    an empty list.

    Parameters
    ----------
    iterate_over_library_output : Iterable
        Pass the output of iterate_over_library to this function
    is_build_callable : callable
    is_testing_dep_callable : callable
    is_runtime_dep_callable : callable

    Returns
    -------
    dict
        keyed on 'testing', 'runtime', 'build' which are the deps for each of
        those phases
    """
    testing = []
    runtime = []
    build = []

    for module_dep_info in iterate_over_library_output:
        build_deps = is_build_callable(module_dep_info)
        runtime_deps = is_runtime_callable(module_dep_info)
        testing_deps = is_testing_callable(module_dep_info)

        build.extend(build_deps)
        runtime.extend(runtime_deps)
        testing.extend(testing_deps)

    return {'testing': testing, 'runtime': runtime, 'build': build}
