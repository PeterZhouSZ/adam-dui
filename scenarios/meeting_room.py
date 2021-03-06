# Copyright 2018 AdaM Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
from common import *

# Create scenario object
scenario = Scenario()

# Add users by name
scenario.add_users_by_names('manager', 'secretary', 'chair', 'employee', 'intern')

# Define all elements and widgets
scenario.add_elements_from_text(
    # Name | Importance | min W | min H | max W | max H | Properties
    #
    # Properties: visual_display, text_input,
    #             touch_pointing, mouse_pointing
    #
    # NOTE: Leave name and importance empty if additional widget type of same element
    '''
    Canvas                 | 10 | 1440 | 900 | 2600 | 1950 | 5050
    Colour Picker          | 12 |   50 |  50 |  200 |  200 | 1052
    Meeting Minutes (view) |  4 |  500 | 400 |  900 | 1200 | 5000
    Meeting Minutes (edit) |  0 |  500 | 500 |  900 | 1300 | 5502
    Time                   |  1 |  100 | 100 |  300 |  200 | 5000
    Calendar               |  1 |  500 | 500 | 1200 |  800 | 5222
    Agenda                 |  3 |  200 | 500 |  500 | 1000 | 5000
    Personal Notes         |  3 |  400 | 500 |  800 | 1200 | 2511
    Facebook               |  0 |  400 | 600 |  800 | 1200 | 3342
    '''
)

# Define devices and users who can access devices
scenario.add_devices_from_text(
    # Name | Width | Height | Properties | Users
    #
    # Properties: visual_display, text_input,
    #             touch_pointing, mouse_pointing
    '''
    Whiteboard         | 2600 | 1950 | 5050 | manager,secretary,chair,employee,intern
    Laptop (manager)   | 1280 |  720 | 4505 | manager
    Laptop (secretary) | 1280 |  720 | 4505 | secretary
    Laptop (chair)     | 1280 |  720 | 4505 | chair
    Laptop (employee)  | 1280 |  720 | 4505 | employee
    Laptop (intern)    | 1280 |  720 | 4505 | intern
    Tablet (manager)   | 1024 |  600 | 3250 | manager
    Tablet (employee)  | 1024 |  600 | 3250 | employee
    Phone (employee)   |  400 |  700 | 2340 | employee
    Phone (intern)     |  400 |  700 | 2340 | intern
    Watch (secretary)  |  200 |  200 | 1010 | secretary
    Watch (chair)      |  200 |  200 | 1010 | chair
    '''
)

# User-specific importance values should be >= 0
# Default value is pre-defined element importance.
# See above for element importance definitions.
scenario.set_user_importance('manager', 'Calendar', 20)

scenario.set_user_importance('chair', 'Agenda', 20)
scenario.set_user_importance('chair', 'Time', 20)

scenario.set_user_importance('employee', 'Facebook', 8)

scenario.set_user_importance('intern', 'Personal Notes', 10)

scenario.set_user_importance('secretary', 'Meeting Minutes (edit)', 10)

# Now run optimizer and tests.
# Specified expectations will be checked when run() is called.
# To test for non-assignment of elements, prepend element name
# with ~, for example: ~comments
scenario.run(expect={
    'Laptop (secretary)': ['Meeting Minutes (edit)'],
    'Laptop (manager)': ['Calendar'],
    'Laptop (intern)': ['Personal Notes'],
    'Tablet (employee)': ['Facebook'],
    'Phone (employee)': ['Colour Picker'],
    'Phone (intern)': ['Colour Picker'],
    'Watch (secretary)': ['Colour Picker'],
    'Watch (chair)': ['Time'],
})

