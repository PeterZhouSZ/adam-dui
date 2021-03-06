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
import time

from gurobipy import *
import numpy as np

def optimize(elements, devices, users):
    """Perform assignment of elements to devices.

    Input:
        elements (list of Element)
        devices (list of Device)
        users (list of User)

    Output:
        dict (Device => list of Element)
        {
            Device1: [Element1, Element2],
            Device2: [Element1, Element3],
            Device3: [Element1],
        }
    """
    elements.sort(key=lambda x: x.name)
    devices.sort(key=lambda x: x.name)
    users.sort(key=lambda x: x.name)

    # Is there sufficient information to solve the assignment problem?
    if len(users) == 0 or len(devices) == 0 or len(elements) == 0:
        output = {}
        for device in devices:
            output[device] = []
        return output, 0.0

    # Form input data
    element_user_imp, element_device_imp, element_device_comp, user_device_access, \
    user_element_access = pre_process_objects(elements, devices, users)

    start_time = time.time()

    # np.set_printoptions(precision=1)
    # print('element_user_imp:\n%s' % element_user_imp)
    # print('element_device_comp:\n%s' % element_device_comp)
    # print('element_device_imp:\n%s' % element_device_imp)
    # print('user_device_access:\n%s' % user_device_access)

    # Create empty model
    model = Model('device_assignment')
    model.params.LogToConsole = 0  # Uncomment to see logs in console

    # (2) Add decision variables
    x = {}
    s = {}
    for e, element in enumerate(elements):
        for d, device in enumerate(devices):
            x[e, d] = model.addVar(vtype=GRB.BINARY,
                                   name='x_%s_%s' % (element.name, device.name))
            s[e, d] = model.addVar(vtype=GRB.SEMIINT,
                                   name='s_%s_%s' % (element.name, device.name))
    model.update()

    for d, device in enumerate(devices):
        # (10) sum of widget areas shouldn't exceed device capacity (area)
        model.addConstr(quicksum(s[e, d] for e, _ in enumerate(elements)) <= device._area,
                        'capacity_constraint_%s' % device.name)

        for e, element in enumerate(elements):
            # (11) the min. width/height of an element should not exceed device width/height
            if element.min_width > device.width or element.min_height > device.height:
                model.addConstr(x[e, d] == 0,
                                'min_size_exceeds_constraint_%s_on_%s' % (element.name, device.name))

            # (9) Set s to zero if x is zero
            model.addGenConstrIndicator(x[e, d], False, s[e, d] == 0)

            # (9) Ensure s within possible min/max
            model.addGenConstrIndicator(x[e, d], True, s[e, d] >= element._min_area)
            model.addGenConstrIndicator(x[e, d], True, s[e, d] <= min(element._max_area, device._area))

    model.update()

    # Make sure element privacy is respected.
    # All users must have access to a device as well as assigned elements.
    # That is, if there is even one user who is not authorised to view an element, the element
    # should not be assigned to the device.
    element_device_access = np.ones((len(elements), len(devices)), dtype=bool)
    for d, device in enumerate(devices):
        for e, element in enumerate(elements):
            # (12) user has no access to element so don't assign to user's device
            if not np.any(np.dot(user_device_access[:, d], user_element_access[:, e])):
                element_device_access[e, d] = 0

    model.update()

    for d, device in enumerate(devices):
        for e, element in enumerate(elements):
            # Do not assign inaccessible elements
            if element_device_access[e, d] == 0:
                model.addConstr(x[e, d] == 0,
                                name='privacy_%s_%s' % (element.name, device.name))

            # (14) Do not assign 0-importance elements
            elif element_device_imp[e, d] < 1e-5:
                element_device_access[e, d] = 0
                model.addConstr(x[e, d] == 0,
                                name='zero_importance_%s_%s' % (element.name, device.name))

            # (14) Do not assign 0-compatibility elements
            elif element_device_comp[e, d] < 1e-5:
                element_device_access[e, d] = 0
                model.addConstr(x[e, d] == 0,
                                name='zero_compatibility_%s_%s' % (element.name, device.name))
    model.update()

    for d, device in enumerate(devices):
        if not np.any(element_device_access[:, d]):
            # (13) a device which is not accessible by any user should not have a element
            model.addConstr(quicksum(x[e, d] for e, _ in enumerate(elements)) == 0,
                            'no_element_constraint_%s' % device.name)
    model.update()

    # Elements Diversity
    user_num_elements = {}
    user_has_element = {}
    user_num_unique_elements = {}
    user_num_replicated_elements = {}
    for u, user in enumerate(users):
        user_elements = [(e, element) for e, element in enumerate(elements) if user_element_access[u, e]]
        user_devices = [(d, device) for d, device in enumerate(devices) if user_device_access[u, d]]

        for e, element in user_elements:
            user_num_elements[u, e] = model.addVar(vtype=GRB.SEMIINT)
            model.addConstr(user_num_elements[u, e]
                            == quicksum(x[e, d] for d, _ in user_devices))

            # (6) whether element has been made available to user
            user_has_element[u, e] = model.addVar(vtype=GRB.SEMIINT)
            model.addConstr(user_has_element[u, e] <= user_num_elements[u, e])
            model.addConstr(user_has_element[u, e] <= 1)

            user_num_replicated_elements[u, e] = model.addVar(vtype=GRB.SEMIINT)
            model.addConstr(user_num_replicated_elements[u, e] + 1 >=
                            quicksum(x[e, d] for d, device in user_devices))

        user_num_unique_elements[u] = model.addVar(vtype=GRB.SEMIINT)
        model.addConstr(user_num_unique_elements[u] ==
                        quicksum(user_has_element[u, e] for e, element in user_elements))

    # (7) completeness ratio of user with min. completeness
    min_ratio_unique_elements = model.addVar(vtype=GRB.CONTINUOUS, lb=0.0)
    for u, user in enumerate(users):
        user_elements = [(e, element) for e, element in enumerate(elements) if user_element_access[u, e]]
        num_user_elements = len(user_elements)
        if num_user_elements > 0:
            model.addConstr(min_ratio_unique_elements <= user_num_unique_elements[u] / num_user_elements)

    # Objective function
    quality_term      = 0.0
    completeness_term = 0.0

    quality_weight      = 0.8
    completeness_weight = 0.2
    # assert np.abs(compatibility_weight + quality_weight + completeness_weight - 1.0) < 1e-6

    for d, device in enumerate(devices):
        # (3)
        # Maximize summed area of elements weighted by importance
        # Also maximize compatibility in assignment
        quality_term += quicksum(
                    element_device_comp[e, d] * element_device_imp[e, d] * s[e, d]
                    for e, element in enumerate(elements)
                ) / (device._area)

    # (8) Term for trying to assign all available elements
    for u, user in enumerate(users):
        user_devices = [(d, device) for d, device in enumerate(devices) if user_device_access[u, d]]
        user_elements = [(e, element) for e, element in enumerate(elements) if user_element_access[u, e]]
        if len(user_devices) > 0 and len(user_elements) > 0:
            completeness_term += quicksum(
                user_has_element[u, e]
                for e, element in user_elements
            ) / (len(user_elements) * len(users))

    # (8) Additional term: ensure minimum coverage is optimized more
    completeness_term += min_ratio_unique_elements

    # (1) Register objective function terms
    model.ModelSense = GRB.MAXIMIZE
    model.setObjectiveN(
        quality_term,
        index=0,
        weight=quality_weight,
        priority=0,
    )
    model.setObjectiveN(
        completeness_term,
        index=1,
        weight=completeness_weight,
        priority=0,
    )

    # Create output list of elements (sorted)
    output = {}
    for device in devices:
        output[device] = []

    # Solve
    model.optimize()
    end_time = time.time()
    time_taken = end_time - start_time
    if model.status != GRB.status.OPTIMAL:
        return output, time_taken

    # for d, device in enumerate(devices):
    #     for e, element in enumerate(elements):
    #         print('%s [%d] - %s [%d] has size %d' % (device.name, d, element.name, e, s[e, d].x))

    # for e, element in enumerate(elements):
    #     for d, device in enumerate(devices):
    #         x_ = x[e,d].x
    #         s_ = s[e,d].x
    #         print('(%d,%d): x = %d, s = %d' % (e, d, x_, s_))

    # for u, user in enumerate(users):
    #     user_elements = [(e, element) for e, element in enumerate(elements) if user_element_access[u, e]]
    #     for e, element in user_elements:
    #         print('user_num_elements[%s, %s] = %d'
    #               % (user.name, element.name, user_num_elements[u, e].x))
    #         print('user_has_element[%s, %s] = %d'
    #               % (user.name, element.name, user_has_element[u, e].x))
    #         print('user_num_replicated_elements[%s, %s] = %d'
    #               % (user.name, element.name, user_num_replicated_elements[u, e].x))

    # for u, user in enumerate(users):
    #     user_assigned_elements = np.unique(sorted([element.name
    #           for d, _ in enumerate(devices)
    #           for e, element in enumerate(elements)
    #           if x[e, d].x == 1 and user_device_access[u, d]]))
    #     print('%s has %d elements assigned:\n> %s' %
    #           (user.name, len(user_assigned_elements), ', '.join(user_assigned_elements)))

    print('Coverages:')
    for u, user in enumerate(users):
        user_elements = [(e, element) for e, element in enumerate(elements) if user_element_access[u, e]]
        if len(user_elements) > 0:
            print('- %s: %.2f' % (user.name, user_num_unique_elements[u].x / len(user_elements)))
        else:
            print('- %s: 0.0' % user.name)
    print('- min: %.2f' % min_ratio_unique_elements.x)

    # Fill output with optimizer result
    for key, var in x.items():
        if var.x != 1:  # Ignore if not 1.0 (assignment)
            continue
        e, d = key

        element = elements[e]
        device = devices[d]
        if not hasattr(element, '_optimizer_size'):
            element._optimizer_size = {}
        element._optimizer_size[device.name] = s[e, d].x
        output[device].append(element)
    return output, time_taken


def pre_process_objects(elements, devices, users):
    # compatibility_metric = 'distance'
    compatibility_metric = 'dot'

    num_elements = len(elements)
    num_devices = len(devices)
    num_users = len(users)

    # Normalize so values are in [0, 1]
    def normalized(vector):
        v_max = vector.max()
        v_min = 0.0  # vector.min()
        v_dif = v_max - v_min
        vector = vector - v_min
        if v_dif > 1e-6:
            vector = vector / v_dif
        return vector

    # Retrieve, store and normalize user-specific element importance
    element_user_imp = np.zeros((num_elements, num_users))
    element_name_index = dict((element.name, i) for i, element in enumerate(elements))
    for u, user in enumerate(users):
        element_user_imp[:, u] = [element.importance for element in elements]
        for element_name, importance in user.importance.iteritems():
            if element_name in element_name_index:
                element_user_imp[element_name_index[element_name], u] = importance

    # Calculate and create normalized matrix of element-device compatibility
    element_device_comp = np.zeros((num_elements, num_devices))
    for d, device in enumerate(devices):
        for e, element in enumerate(elements):
            element_device_comp[e, d] = device.calculate_compatibility(element, compatibility_metric)
        element_device_comp[:, d] = normalized(element_device_comp[:, d])

    # Set boolean matrix of user-device access
    # TODO: try continuous numbers
    user_device_access = np.zeros((num_users, num_devices), dtype=bool)
    for d, device in enumerate(devices):
        for user in device.users:
            user_device_access[users.index(user), d] = 1

    # Set boolean matrix of user-element access
    user_element_access = np.zeros((num_users, num_elements), dtype=bool)
    for e, element in enumerate(elements):
        for u, user in enumerate(users):
            # NOTE: we set access to False if importance 0
            if element.user_has_access(user):
                user_element_access[u, e] = 1
            else:
                element_user_imp[e, u] = 0

    element_user_imp = np.multiply(element_user_imp, user_element_access.transpose())
    for u, user in enumerate(users):
        element_user_imp[:, u] = normalized(element_user_imp[:, u])

    # If close to zero importance, set access to 0
    for e, element in enumerate(elements):
        for u, user in enumerate(users):
            if element_user_imp[e, u] < 1e-6:
                user_element_access[u, e] = 0

    # Normalize element importances per device
    element_device_imp = np.asmatrix(element_user_imp) * np.asmatrix(user_device_access)
    for d, device in enumerate(devices):
        num_users_on_device = np.sum(user_device_access[:, d])
        if num_users_on_device > 0:
            element_device_imp[:, d] /= num_users_on_device

    # Set accumulated element-device to zero if no users with access to both e and d
    for d, device in enumerate(devices):
        for e, element in enumerate(elements):
            comp = np.multiply(user_element_access[:, e], user_device_access[:, d])
            if np.count_nonzero(user_device_access[:, d]) > 1 and np.count_nonzero(comp) == 1:
                element_device_imp[e, d] = 0
                for u, v in enumerate(comp):
                    if v == 0:
                        user_element_access[u, e] = 0
        element_device_imp[:, d] = normalized(element_device_imp[:, d])

    # Add noise to prevent stalemates
    def add_noise(array):
        nonzero_indices = np.nonzero(array)
        array[nonzero_indices] += 0.05 * np.random.random(size=array.shape)[nonzero_indices]
    # add_noise(element_device_comp)
    # add_noise(element_device_imp)
    # add_noise(element_user_imp)

    return element_user_imp, element_device_imp, element_device_comp, user_device_access, \
           user_element_access
