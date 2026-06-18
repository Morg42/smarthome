#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-       Martin Sinn                         m.sinn@gmx.de
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
This script converts the configuration files of SmartHomeNG from the old CONF
format to the newly supported YAML format.

It asks if it should convert the items and/or the configuration of SmartHomnNG.

The old files remain in their directories. The `item/*.conf` files have to be
moved/deleted to prevent the items from being read two times.
The ``etc/*.conf`` files can remain in position (or can be moved/deleted as
well). If a configuration exists in ``etc`` in both file formats, the YAML file
will be used.
"""

import os
import sys
from pathlib import Path

print('')
print(os.path.basename(__file__) + ' - Tool zur Konvertierung von shng .conf-Dateien ins yaml-Format')
print('')

#####################################################################
# Check Python Version
#####################################################################
if sys.hexversion < 0x03030000:
    print(
        f'Der Python-Interpreter ({sys.version_info[0]}.{sys.version_info[1]}) ist zu alt. Bitte mindestens auf Python 3.3 aktualisieren.'
    )
    exit()

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.chdir('..')
sys.path.insert(0, 'lib')

import item_conversion  # type: ignore # import path changed dynamically

# ==================================================================================
#   Convert all .conf files in a directory
#


def _convert_directory(dir):

    print(f'Konvertiere Dateien in {dir}:')
    for item_file in sorted(Path(dir).glob('*.conf')):
        # Remove path and extension
        configurationfile = Path(*item_file.parts[:-1], item_file.stem)

        ydata = item_conversion.parse_for_convert(str(configurationfile) + '.conf')
        if not ydata:
            continue
        try:
            item_conversion.yaml_save(str(configurationfile), ydata)
        except Exception as e:
            print(f'Fehler beim Lesen von {configurationfile}: {e}')
        else:
            # as rename overwrites, which is not wanted, we test for existing file
            if not Path.is_file(configurationfile.with_suffix('.conf.old')):
                Path.rename(configurationfile.with_suffix('.conf'), configurationfile.with_suffix('.conf.old'))
            else:
                print(f'Fehler beim Umbenennen, bitte {configurationfile}.conf von Hand entfernen.')


# ==================================================================================
#   Main Converter Routine
#

if __name__ == '__main__':
    if item_conversion.is_ruamelyaml_installed() is False:
        print('Fehler: ruamel.yaml nicht installiert.')
        exit(1)

    # subdirs possible for conf files
    dirs_old = ['items', 'scenes', 'structs']

    # join all dirs
    # in later release, remove '+ dirs_old'
    dirs = ['etc'] + dirs_old + [os.path.join('etc', dir) for dir in dirs_old]

    # just keep those which are dirs and contain conf files
    do_dirs = [dir for dir in dirs if os.path.isdir(dir) and list(Path(dir).glob('*.conf'))]

    for dir in do_dirs:
        if os.listdir(dir):
            if input(f'Dateien im Verzeichnis {dir} konvertieren (j/n)? ').lower() == 'j':
                _convert_directory(dir)
