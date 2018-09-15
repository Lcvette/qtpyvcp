#!/usr/bin/env python
# coding: utf-8

#   Copyright (c) 2018 Kurt Jacobson
#      <kurtcjacobson@gmail.com>
#
#   This file is part of QtPyVCP.
#
#   QtPyVCP is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 2 of the License, or
#   (at your option) any later version.
#
#   QtPyVCP is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with QtPyVCP.  If not, see <http://www.gnu.org/licenses/>.

# Description:
#   LinuxCNC coolant actions

import sys
import linuxcnc
from PyQt5.QtWidgets import QAction

# Set up logging
from QtPyVCP.utilities import logger
LOG = logger.getLogger(__name__)

from QtPyVCP.utilities.status import Status, Info
from QtPyVCP.actions.base_actions import setTaskMode

STATUS = Status()
INFO = Info()
STAT = STATUS.stat
CMD = linuxcnc.command()

def bindWidget(widget, action):
    """Binds a widget to a program action.

    Args:
        widget (QtWidget) : The widget to bind the action too. Typically `widget`
            would be a QPushButton, QCheckBox or a QAction.

        action (string) : The string identifier of the machine action to bind
            the widget to in the format `action_class.action_name:arg`.
    """
    action, sep, arg = action.partition(':')
    action = action.replace('-', '_')
    method = reduce(getattr, action.split('.'), sys.modules[__name__])
    if method is None:
        return

    if isinstance(widget, QAction):
        sig = widget.triggered
    else:
        sig = widget.clicked

    if arg == '':
        sig.connect(method)
    else:
        if arg.isdigit():
            arg = int(arg)
        sig.connect(lambda: method(arg))

    # if it is a toggle action make the widget checkable
    if action.endswith('toggle'):
        widget.setCheckable(True)

    if action.startswith('estop'):
        STATUS.estop.connect(lambda v: widget.setChecked(not v))

    elif action.startswith('power'):
        power.ok(widget)
        STATUS.estop.connect(lambda: power.ok(widget))
        STATUS.on.connect(lambda v: widget.setChecked(v))

    elif action == 'home.all':
        home.ok(-1, widget)
        STATUS.on.connect(lambda: home.ok(-1, widget))
        STATUS.homed.connect(lambda: home.ok(-1, widget))

    elif action == 'home.joint':
        home.ok(arg, widget)
        STATUS.on.connect(lambda: home.ok(arg, widget))
        STATUS.homed.connect(lambda: home.ok(arg, widget))

    elif action == 'home.axis':
        axis = getAxisLetter(arg)
        jnum = INFO.AXIS_LETTER_LIST.index(arg.lower())
        home.ok(arg, widget)
        STATUS.on.connect(lambda: home.ok(jnum, widget))

class estop:
    """E-Stop action group"""
    @staticmethod
    def activate():
        """Set E-Stop active"""
        LOG.debug("Setting state red<ESTOP>")
        CMD.state(linuxcnc.STATE_ESTOP)

    @staticmethod
    def reset():
        """Resets E-Stop"""
        LOG.debug("Setting state green<ESTOP_RESET>")
        CMD.state(linuxcnc.STATE_ESTOP_RESET)

    @staticmethod
    def toggle():
        """Toggles E-Stop state"""
        if estop.is_activated():
            estop.reset()
        else:
            estop.activate()

    @staticmethod
    def is_activated():
        """Checks if E_Stop is activated.

        Returns:
            bool : True if E-Stop is active, else False.
        """
        return bool(STAT.estop)

    @staticmethod
    def ok(widget=None):
        # E-Stop is ALWAYS ok, but provide this method for consistency
        estop.ok.msg = ""
        return True

class power:
    """Power action group"""
    @staticmethod
    def on():
        """Turns machine power On"""
        LOG.debug("Setting state green<ON>")
        CMD.state(linuxcnc.STATE_ON)

    @staticmethod
    def off():
        """Turns machine power Off"""
        LOG.debug("Setting state red<OFF>")
        CMD.state(linuxcnc.STATE_OFF)

    @staticmethod
    def toggle():
        """Toggles machine power On/Off"""
        if power.is_on():
            power.off()
        else:
            power.on()

    @staticmethod
    def is_on():
        """Checks if power is on.

        Returns:
            bool : True if power is on, else False.
        """
        return STAT.task_state == linuxcnc.STATE_ON

    @staticmethod
    def ok(widget=None):
        if STAT.task_state == linuxcnc.STATE_ESTOP_RESET:
            okey = True
            msg = "Turn machine on"
        else:
            okey = False
            msg = "Can't turn machine ON until out of E-Stop"

        power.ok.msg = msg

        if widget is not None:
            widget.setEnabled(okey)
            widget.setStatusTip(msg)
            widget.setToolTip(msg)

        return okey

class home:
    @staticmethod
    def all():
        """Homes all axes."""
        LOG.info("Homing all axes")
        _home_joint(-1)

    @staticmethod
    def axis(axis):
        """Home a specific axis.

        Args:
            axis (int | str) : Either the axis letter or number to home.
        """
        axis = getAxisLetter(axis)
        if axis.lower() == 'all':
            home.all()
            return
        jnum = INFO.COORDINATES.index(axis)
        LOG.info('Homing Axis: {}'.format(axis.upper()))
        _home_joint(jnum)

    @staticmethod
    def joint(jnum):
        """Home a specific joint.

        Args:
            jnum (int) : The number of the joint to home.
        """
        LOG.info("Homing joint: {}".format(jnum))
        _home_joint(jnum)

    @staticmethod
    def ok(jnum, widget=None):
        if power.is_on(): # and not STAT.homed[jnum]:
            okay = True
            msg = ""
        else:
            okay = False
            msg = "Machine must be on to home"

        home.ok.msg = msg

        if widget is not None:
            widget.setEnabled(okay)
            widget.setStatusTip(msg)
            widget.setToolTip(msg)

        return okay

class unhome:
    @staticmethod
    def all():
        pass

    @staticmethod
    def axis(axis):
        pass

    @staticmethod
    def joint(jnum):
        pass

def _home_joint(jnum):
    setTaskMode(linuxcnc.MODE_MANUAL)
    CMD.teleop_enable(False)
    CMD.home(jnum)

def _unhome_joint(jnum):
    setTaskMode(linuxcnc.MODE_MANUAL)
    CMD.teleop_enable(False)
    CMD.home(jnum)

# Homing helper functions

def getAxisLetter(axis):
    """Takes an axis letter or number and returns the axis letter.

    Args:
        axis (int | str) : Either a axis letter or an axis number.

    Returns:
        str : The axis letter, `all` for an input of -1.
    """
    if isinstance(axis, int):
        return ['x', 'y', 'z', 'a', 'b', 'c', 'u', 'v', 'w', 'all'][axis]
    return axis.lower()

def getAxisNumber(axis):
    """Takes an axis letter or number and returns the axis number.

    Args:
        axis (int | str) : Either a axis letter or an axis number.

    Returns:
        int : The axis number, -1 for an input of `all`.
    """
    if isinstance(axis, str):
        return ['x', 'y', 'z', 'a', 'b', 'c', 'u', 'v', 'w', 'all'].index(axis.lower())
    return axis
