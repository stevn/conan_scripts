#!/usr/bin/env python3

"""Install a Conan package with original dependencies."""

# pylint: disable=line-too-long

import argparse
import subprocess
import configparser
import json
import sys
import re


def get_conan_ini_parser():
    """Get the .ini file parser that is compatible with Conan-generated config files (Conan profiles, conaninfo.txt, etc)."""
    return configparser.ConfigParser(allow_no_value=True, strict=False, delimiters=['='])


def get_full_query_from_profile(conan_profile_path: str, conan_options: list, conan_settings: list) -> str:
    """Get Conan search query argument from Conan profile."""
    print()
    print('Getting Conan search query argument from Conan profile.')

    queries = {}

    # Start with queries from Conan profile
    profile = get_conan_ini_parser()
    profile.read(conan_profile_path)
    for section_name in profile.sections():
        print('section_name:', section_name)
        if section_name == 'settings' or section_name == 'options':
            section = profile[section_name]
            for key in section:
                if key.endswith('_build'):
                    continue
                val = section[key]
                if re.search(r'\s', val):
                    val = '"' + val + '"'
                queries[key] = val

    # Explicit Conan options override profile
    for conan_option in conan_options:
        parts = conan_option.split('=')
        if len(parts) != 2:
            raise ValueError("Could not parse conan option (expected format is option=value): " + conan_option)
        key, val = parts
        queries[key] = val

    # Explicit Conan settings override profile + options
    for conan_setting in conan_settings:
        parts = conan_setting.split('=')
        if len(parts) != 2:
            raise ValueError("Could not parse conan setting (expected format is option=value): " + conan_setting)
        key, val = parts
        queries[key] = val

    full_query = ' AND '.join([key  + '=' + val for key, val in queries.items()])
    return full_query


def get_package_id(package_reference: str, conan_remote: str, full_query: str) -> str:
    """Get the Conan package ID for a given profile query."""
    print()
    print('Getting the Conan package ID for a given profile query...')
    conan_search_json_path = 'conan_search.json'
    cmd = [
        'conan',
        'search',
        '-q',
        full_query,
        '-r',
        conan_remote,
        '-j',
        conan_search_json_path,
        package_reference,
    ]
    print('Running cmd:', subprocess.list2cmdline(cmd))
    subprocess.check_call(cmd)

    with open(conan_search_json_path, encoding='utf-8') as f:
        j = json.load(f)

    results = j['results']
    if not results:
        raise ValueError("Could not find any matching Conan packages on remote!")
    if len(results) > 1:
        print("WARNING: multiple matching packages found, choosing first one!")
    chosen_result = results[0]

    items = chosen_result['items']
    if not items:
        raise ValueError("Could not find any matching Conan packages on remote!")
    if len(items) > 1:
        print("WARNING: multiple matching packages found, choosing first one!")
    chosen_item = items[0]

    packages = chosen_item['packages']
    if not packages:
        raise ValueError("Could not find any matching Conan packages on remote!")
    if len(packages) > 1:
        print("WARNING: multiple matching packages found, choosing first one!")
    chosen_package = packages[0]

    package_id = chosen_package['id']
    return package_id


def get_conan_info(full_reference: str, conan_remote: str, conan_info_file_path: str):
    """Get the Conan build info txt file from remote."""
    print()
    print('Getting the Conan build-time information from remote...')

    # List files in remote directory
    # cmd = [
    #     'conan',
    #     'get',
    #     '-r',
    #     conan_remote,
    #     full_reference,
    #     '.',
    # ]
    # print("Running cmd:", subprocess.list2cmdline(cmd))
    # subprocess.check_call(cmd)

    # Download conaninfo from remote
    cmd = [
        'conan',
        'get',
        '-r',
        conan_remote,
        full_reference,
        'conaninfo.txt',
    ]
    with open(conan_info_file_path, 'w', encoding='utf-8') as f:
        print("Running cmd:", subprocess.list2cmdline(cmd))
        subprocess.check_call(cmd, stdout=f)


def get_dependencies_from_conan_info(conan_info_file_path: str) -> list:
    """Parse the conan build info file and return the list of dependencies used at build time."""
    print()
    print('Getting build-time versions of dependencies...')
    build_info = get_conan_ini_parser()
    build_info.read(conan_info_file_path)
    deps = []
    for section_name in build_info.sections():
        if section_name == 'full_requires':
            section = build_info[section_name]
            for key in section:
                print(key)
                key = key.split(':')
                deps.append(key[0])
    return deps


def install(package_reference: str, conan_remote: str, conan_profile_path: str, deps: list, conan_options: list, conan_settings: list):
    """Install the conan package with the build-time versions of the dependencies."""
    print()
    print('Installing the conan package with the build-time versions of the dependencies...')
    cmd = [
        'conan',
        'install',
        '-r',
        conan_remote,
        '-pr',
        conan_profile_path,
    ]
    for dep in deps:
        cmd.append('--require-override')
        cmd.append(dep)
    for conan_option in conan_options:
        cmd.append('-o')
        cmd.append(conan_option)
    for conan_setting in conan_settings:
        cmd.append('-s')
        cmd.append(conan_setting)
    cmd.append(package_reference)
    print('Running cmd:', subprocess.list2cmdline(cmd))
    subprocess.check_call(cmd)


def install_pkg(package_reference: str, conan_remote: str, conan_profile_path: str, conan_options: list, conan_settings: list):
    """Install a Conan package with original dependencies."""
    full_query = get_full_query_from_profile(conan_profile_path, conan_options=conan_options, conan_settings=conan_settings)
    print('Full query:', full_query)

    package_id = get_package_id(package_reference=package_reference, conan_remote=conan_remote, full_query=full_query)
    full_reference = package_reference + ':' + package_id
    print("Using full package reference with package ID: " + full_reference)

    conan_info_file_path = 'conaninfo.txt'
    get_conan_info(full_reference=full_reference, conan_remote=conan_remote, conan_info_file_path=conan_info_file_path)

    deps = get_dependencies_from_conan_info(conan_info_file_path)
    print("Dependencies:", deps)

    install(package_reference=package_reference, conan_remote=conan_remote, conan_profile_path=conan_profile_path, deps=deps, conan_options=conan_options, conan_settings=conan_settings)
    print('Done.')


def install_main(input_args):
    """Main CLI function."""

    desc = """Install a Conan package with original dependencies.

Example: ./install.py my_app/1.2.3@user/channel -o my_option1=False -o my_option2=True -s build_type=Release -s arch=x86_64 -r myremote -pr ../myprofiles/mac
"""

    parser = argparse.ArgumentParser(description=desc, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--remote', '-r', help='Conan remote (required).', required=True)
    parser.add_argument('--profile', '-pr', help='Conan profile filename to install the package for (required).', required=True)
    parser.add_argument('--options', '-o', help='Conan package options (optional).', default=[], action='append')
    parser.add_argument('--settings', '-s', help='Conan package settings (optional).', default=[], action='append')
    parser.add_argument('reference', help='Conan package reference in format name/version@user/channel (required).')
    args = parser.parse_args(args=input_args)

    install_pkg(
        package_reference=args.reference,
        conan_remote=args.remote,
        conan_profile_path=args.profile,
        conan_options=args.options,
        conan_settings=args.settings,
        )


if __name__ == "__main__":
    install_main(sys.argv[1:])
