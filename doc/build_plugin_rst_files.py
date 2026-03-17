#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017-       Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################


"""
This script creates the files for including the plugin documentation into the developer- and
user-documentation.

it creates the files:

- plugins_gateway.rst
- plugins_interface.rst
- plugins_protocol.rst
- plugins_system.rst
- plugins_unclassified.rst
- plugins_web.rst

in the directory **../doc/<user/developer>/source/plugins_doc** .

These files contain

- an include for a header file
- a toctree directive
- a table with information about the plugins and links to further information
- an include for a footer file

"""

import os
import subprocess
import sys
import textwrap

print('')
print(os.path.basename(__file__) + ' - Builds the .rst files for the documentation')
print('')
start_dir = os.getcwd()

# find lib directory and import lib/item_conversion
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# um im Test-build_doc Umfeld zu laufen:
sys.path.insert(0, '..')
sys.path.insert(0, '../lib')
import shyaml  # type: ignore  # not in path

type_unclassified = 'unclassified'
plugin_sections = {
    'gateway': {'de': 'Gateway', 'en': 'Gateway'},
    'interface': {'de': 'Interface', 'en': 'Interface'},
    'protocol': {'de': 'Protokoll', 'en': 'Protocol'},
    'system': {'de': 'System', 'en': 'System'},
    'web': {'de': 'Web/Cloud', 'en': 'Web/Cloud'},
    type_unclassified: {'de': 'nicht klassifizierte', 'en': 'non classified'},
    'all': {'de': 'Alle Plugins', 'en': 'All plugins'},
}

v = {
    'type': {'de': 'Typ', 'en': 'type'},
    'conf': {'de': 'Konfiguration', 'en': 'Configuration'},
    'desc': {'de': 'Beschreibung', 'en': 'Description'},
    'info': {'de': 'zusätzliche Infos', 'en': 'additional information'},
    'supp': {'de': 'Unterstützung', 'en': 'support'},
    'pver': {'de': 'maximale Python-Version', 'en': 'maximum Python version'},
    'sver': {'de': 'maximale SmartHomeNG-Version', 'en': 'maximum SmartHomeNG-Version'},
    'stat': {'de': 'Plugin-Status', 'en': 'Plugin status'},
}

default_lang = 'en'


def bold(s: str) -> str:
    """mark string as bold if not empty"""
    return '**' + s + '**' if s else ''


def get_list_fromgit(name: str):
    """get filelist via git and return all matching files at first directory level"""
    # this could be written as a single nested comprehension, but gets quite unreadable
    # we gain speedup by using comprehensions
    plg_git = (
        subprocess.check_output(['git', 'ls-files', f'*/{name}'], stderr=subprocess.STDOUT)
        .decode()
        .strip('\n')
        .split('\n')
    )
    plglist = [x[0] for x in (p.split('/') for p in plg_git) if x[1] == name]
    return plglist


def get_pluginlist_fromgit():
    """get filelist of __init__.py files"""
    return get_list_fromgit('__init__.py')


def get_local_pluginlist():
    """like get_list_fromgit, but list files from local dir"""
    plglist = [x for x in os.listdir('.') if x[0] not in ['.', '_'] and x != 'deprecated_plugins']
    return plglist


def get_pluginyamllist_fromgit():
    """get filelist of plugin.yaml files"""
    return get_list_fromgit('plugin.yaml')


def get_description(section_dict: dict, lang: str = 'en') -> str:
    """get description from dict in specified or fallback language as single line string"""
    desc = ''
    try:
        desc = (section_dict['description'].get(lang, '') or '').replace('\n', ' ')
    except Exception:
        pass
    if not desc:
        try:
            lang2 = 'de' if lang == 'en' else default_lang
            desc = (section_dict['description'].get(lang2, '') or '').replace('\n', ' ')
        except Exception:
            pass
    return desc


def get_info(from_dict: dict, section: str, link: bool = False) -> str:
    # as None can be returned as a value, or-it with '' to guarantee a str
    # remove newlines as we don't need visual layout
    text = (from_dict.get(section, '') or '').replace('\n', ' ')

    if link and text and not text.startswith('https://'):
        text = 'https://' + text
    if link:
        text = html_escape(text)
    return text


def get_version(section_dict: dict) -> str:
    """return version from dict with v or empty string"""
    version = section_dict.get('version', '')
    if version != '':
        version = 'v' + version
    return version


def html_escape(str) -> str:
    """minimal html escape for umlauts"""
    html = (
        str.rstrip().replace('ä', '&auml;').replace('ö', '&ouml;').replace('ü', '&uuml;')
        if str
        else ''
    )
    return html


def build_pluginlist(plugins: list[str], language: str = 'de') -> dict:
    """
    Return a list of dicts with a dict for each plugin of the requested type
    The dict contains the plugin name, type and description as strings
    """
    results = {type_: list() for type_ in plugin_sections}

    # prevent division by zero
    if not plugins:
        return results

    num_pl = len(plugins)
    count = 0

    # read all plugins once
    for metaplugin in plugins:
        count += 1
        print(f'Lese Metadaten: {int(100 * count / num_pl)}%\r', end='')
        plg_dict = {}
        plg_dict['name'] = metaplugin.lower()
        plg_dict['type'] = type_unclassified
        plgtype = type_unclassified

        metafile = os.path.join(metaplugin, 'plugin.yaml')
        plugin_yaml = shyaml.yaml_load(metafile)
        if plugin_yaml:
            section_dict = plugin_yaml.get('plugin')
            if section_dict:
                plg_dict['version'] = get_version(section_dict)
                plg_dict['sh_minversion'] = str(section_dict.get('sh_minversion', ''))
                plg_dict['sh_maxversion'] = str(section_dict.get('sh_maxversion', ''))
                plg_dict['py_minversion'] = str(section_dict.get('py_minversion', ''))
                plg_dict['py_maxversion'] = str(section_dict.get('py_maxversion', ''))

                try:
                    if section_dict['type'].lower() in plugin_sections:
                        plgtype = section_dict['type'].lower()
                except Exception:
                    pass
                plg_dict['type'] = plgtype

                plg_dict['desc'] = get_description(section_dict, language)
                plg_dict['maint'] = get_info(section_dict, 'maintainer')
                plg_dict['test'] = get_info(section_dict, 'tester')

                plg_dict['state'] = get_info(section_dict, 'state')
                plg_dict['doc'] = get_info(section_dict, 'documentation', link=True)
                plg_dict['sup'] = get_info(section_dict, 'support', link=True)

        else:
            plg_dict['version'] = ''
            plg_dict['desc'] = 'No metadata (plugin.yaml) was provided for this plugin!'
            plg_dict['maint'] = ''
            plg_dict['test'] = ''
            plg_dict['doc'] = ''
            plg_dict['sup'] = ''

        results[plgtype].append(plg_dict)
        results['all'].append(plg_dict)
        # print(f'added {metaplugin} to {plgtype}')

    print('\n')
    return results


def flatten(obj):
    """return flat list from nested list"""
    if isinstance(obj, list):
        for item in obj:
            yield from flatten(item)
    else:
        yield obj


def make_table_lines(lines: list, indent: int = 3, top: bool = False, wide: bool = False) -> list:
    """
    take a list and return rST lines

    If top is set, the list looks like
    * - foo
      - bar
      - baz

    If top is not set, the list looks like
    - foo

      bar

      baz
    """

    ind = ' ' * indent

    first, follow = '- ', '  '
    if top:
        first, follow = '* - ', '  - '

    result = []
    if not lines or lines == [None]:
        return []

    for i, line in enumerate(lines):
        if isinstance(line, list):
            if top:
                result += [ind + l for l in line if line]
            else:
                result += [l for x in line if line for l in (ind + x, ind)][:-1]
        else:
            result += [ind + (follow if i else first) + line]
            if wide:
                result += ['']
    if result[-1:] == '':
        del result[-1:]
    return result


def make_table_bullet_lines(lines: list, indent: int = 3) -> list:
    """
    take a list and return rST lines with bullets

    (indented) list looks like

      + foo
      + bar
      + baz

    with correct empty line before and after

    If lines is empty, return
    <empty>
    |br|
    <empty>

    to enforce one empty line
    """
    if not lines or lines == [[], []]:
        return ['', '|br|', '']

    ind = ' ' * indent

    result = ['']
    for line in flatten(lines):
        result += [ind + '+ ' + line]
    result += ['']
    return result


def write_rstfile(
    results, plugin_rst_dir, plgtype='all', plgtype_print='', heading='', language='en'
):
    """
    Create a .rst file for each plugin category
    """

    if not heading:
        title = plgtype + ' Plugins'
    else:
        title = heading

    plglist = [plg_dict for plg_dict in results[plgtype]]

    rst_filename = os.path.join('plugins_doc', 'plugins_' + plgtype.lower() + '.rst')
    rst_dummyname = os.path.join('plugins_doc', 'dummy_' + plgtype.lower() + '.rst')
    print(f'Datei: {rst_filename}{" " * (26 - len(rst_filename))}  -  {len(plglist)} {title}')

    #    print("> Opening file "+plugin_rst_dir+'/'+rst_filename)
    with (
        open(plugin_rst_dir + '/' + rst_filename, 'w') as fh,
        open(plugin_rst_dir + '/' + rst_dummyname, 'w') as fh_dummy,
    ):
        #    fh.write(title+'\n')
        #    fh.write('-'*len(title)+'\n')
        # if plgtype != type_unclassified:
        #     fh.write(f'.. index:: Plugin Type; {plgtype_print}\n\n')
        fh.write(f'.. include:: /plugins_doc/plugins_{plgtype}_header.rst\n\n')

        # write toctree to dummy file to suppress warnings for not included README.md files.
        fh_dummy.write(':orphan:\n')
        fh_dummy.write('\n')
        fh_dummy.write(
            '.. This file is only created to suppress Sphinx warnings about README.md files not beeing included in any toctree.\n'
        )
        fh_dummy.write('\n')
        fh_dummy.write('.. toctree::\n')
        fh_dummy.write('   :maxdepth: 2\n')
        fh_dummy.write('   :glob:\n')
        fh_dummy.write('   :titlesonly:\n')
        fh_dummy.write('   :hidden:\n')
        fh_dummy.write('\n')

        # write toctree
        fh.write('.. toctree::\n')
        fh.write('   :maxdepth: 2\n')
        fh.write('   :glob:\n')
        fh.write('   :titlesonly:\n')
        fh.write('   :hidden:\n')
        fh.write('\n')

        if not plglist:
            if language == 'de':
                fh.write(f'Zur Zeit gibt es keine Plugins des Typs {plgtype_print}.\n')
            else:
                fh.write(f'At the moment there are no plugins of type {plgtype_print}\n')
            return

        for plg in plglist:
            if os.path.isfile(os.path.join(plg['name'], 'README.md')):
                fh_dummy.write(f'   /plugins/{plg["name"]}/README.md\n')

            fp = os.path.join(plg['name'], 'user_doc')
            if os.path.isfile(fp + '.rst') or os.path.isfile(fp + '.md'):
                fh.write(f'   /plugins/{fp}\n')

            # fh.write(f'   config/{plg["name"]}\n')
        fh.write('\n')

        # write table with details
        fh.write(f"""


.. list-table::
   :header-rows: 1

   * - Plugin ({v['conf'][language]})
     - Version
     - {v['desc'][language]}
     - Maintainer
     - Tester""")

        for plg in plglist:
            if os.path.isfile(
                os.path.join(plugin_rst_dir, 'plugins_doc', 'config', plg['name'] + '.rst')
            ):
                # a generated <config>.rst exists
                plg_readme_link = f':doc:`{plg["name"]} <config/{plg["name"]}>`'
            else:
                # no generated <config>.rst exists (for english developer documentation
                plg_readme_link = plg['name']

            plg_doc = ''
            if plg['doc']:
                plg_doc = f'`{plg["name"]} {v["info"][language]} <{plg["doc"]}>`_'

            plg_sup = ''
            if plg['sup']:
                plg_sup = f'`{plg["name"]} {v["supp"][language]} <{plg["sup"]}>`_'

            desc = (
                [plg['desc']]
                + make_table_bullet_lines(
                    [plg_doc if plg['doc'] else []] + [plg_sup if plg['sup'] else []], 0
                )
                + (
                    [f'Plugin {v["type"][language]}: {bold(plg["type"])}']
                    if plgtype == 'all'
                    else []
                )
            )

            if plg.get('py_maxversion'):
                desc += ['', f'{v["pver"][language]}: {bold(plg["py_maxversion"])}']
            if plg.get('sh_maxversion'):
                desc += ['', f'{v["sver"][language]}: {bold(plg["sh_maxversion"])}']
            if plg.get('state', '').lower() in ['deprecated', 'develop']:
                desc += ['', f'{v["stat"][language]}: {bold(plg["state"])}']

            fh.write(
                '\n'
                + '\n'.join(
                    make_table_lines(
                        [
                            plg_readme_link,
                            plg['version'],
                            make_table_lines(desc, 2),
                            make_table_lines(
                                [x.strip() for x in plg['maint'].split(',')], 2, wide=True
                            ),
                            make_table_lines(
                                [x.strip() for x in plg['test'].split(',')], 2, wide=True
                            ),
                            [],
                        ],
                        top=True,
                    )
                )
            )

        fh.write('\n\n.. include:: /plugins_doc/plugins_footer.rst\n')


# ==================================================================================
#   Main Generator Routine
#

if __name__ == '__main__':
    #    print ('Number of arguments:', len(sys.argv), 'arguments.')
    #    print ('Argument List:', str(sys.argv))

    language = 'en'

    if 'de' in sys.argv:
        language = 'de'

    global docu_type
    docu_type = start_dir.split('/')[-1:][0]  # developer / user

    print('Start directory        = ' + start_dir)
    print('Documentation type     = ' + docu_type)
    print('Documentation language = ' + language)
    print('')

    # change the working diractory to the directory from which the converter is loaded (../tools)
    os.chdir(os.path.dirname(os.path.abspath(os.path.basename(__file__))))

    plugindirectory = '../plugins'
    pluginabsdirectory = os.path.abspath(plugindirectory)

    os.chdir(pluginabsdirectory)

    plugins_git = get_pluginlist_fromgit()
    if 'xmpp' not in plugins_git:
        plugins_git.append('xmpp')

    print('--- Liste der Plugins auf github (' + str(len(plugins_git)) + '):')

    pluginsyaml_git = get_pluginyamllist_fromgit()
    if 'xmpp' not in plugins_git:
        plugins_git.append('xmpp')

    print('--- Liste der Plugins mit Metadaten auf github (' + str(len(pluginsyaml_git)) + '):')
    print()

    if docu_type == 'doc':
        plugin_rst_dir = os.path.join(start_dir, 'user', 'source')
    else:
        plugin_rst_dir = os.path.join(start_dir, 'source')
    print('zu schreiben in: ' + plugin_rst_dir)

    results = build_pluginlist(plugins_git, language)

    for pl in plugin_sections:
        if results[pl] is None:
            print(f'Datei: plugins_doc/plugins_{pl.lower()}.rst: Daten unverändert, übersprungen')
        else:
            write_rstfile(
                results, plugin_rst_dir, pl, plugin_sections[pl][language], language=language
            )
    print()
