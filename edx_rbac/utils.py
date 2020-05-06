# -*- coding: utf-8 -*-
"""
Utils for 'edx-rbac' module.
"""
from __future__ import absolute_import, unicode_literals

import importlib
from collections import defaultdict

from django.apps import apps
from django.conf import settings
from six import string_types

ALL_ACCESS_CONTEXT = '*'


def request_user_has_implicit_access_via_jwt(decoded_jwt, role_name, context=None):
    """
    Check the request's user access by mapping user's roles found in jwt to local feature roles.

    decoded_jwt is a dict
    role_name is a string
    context is anything

    Returns a boolean.

    Mapping should be in settings and look like:

        SYSTEM_TO_FEATURE_ROLE_MAPPING = {
            'enterprise_admin': ['coupon-management', 'data_api_access'],
            'enterprise_leaner': [],
            'coupon-manager': ['coupon-management']
        }
    """
    if not decoded_jwt:
        return False

    feature_roles = feature_roles_from_jwt(decoded_jwt)

    if role_name in feature_roles:
        if not context:
            return True
        else:
            return context in feature_roles[role_name] or ALL_ACCESS_CONTEXT in feature_roles[role_name]

    return False


def feature_roles_from_jwt(decoded_jwt):
    """
    Get the mapping of feature roles to roles found in the given JWT.

    Given a decoded JWT, returns a mapping of feature role names to list of
    contexts for which that role name applies.  A "context" here usually
    means the primary identifier of some resource.
    """
    jwt_roles_claim = decoded_jwt.get('roles', [])

    feature_roles = defaultdict(list)

    for role_data in jwt_roles_claim:
        # split should be more robust because of our cousekeys having colons
        role_in_jwt, __, context_in_jwt = role_data.partition(':')
        mapped_roles = settings.SYSTEM_TO_FEATURE_ROLE_MAPPING.get(role_in_jwt, [])
        for role in mapped_roles:
            feature_roles[role].append(context_in_jwt)

    return feature_roles


def user_has_access_via_database(user, role_name, role_assignment_class, context=None):
    """
    Check if there is a role assignment for a given user and role.

    The role object itself is found via the role_name. The role_assignment_class's get_context() method can return a
    single context string which could be an ALL_ACCESS_CONTEXT or, incase of multiple user contexts, a list of strings.
    The context argument is evaluated against the context(s) received from the role_assignment_class while accounting
    for the ALL_ACCESS_CONTEXT to grant access.
    """
    if getattr(user, 'is_anonymous', False):
        return False

    role_assignments = role_assignment_class.objects.filter(user=user, role__name=role_name)

    if not role_assignments:
        return False

    if not context:
        return True

    assigned_contexts = set()

    for assignment in role_assignments:
        context_in_database = assignment.get_context()
        if isinstance(context_in_database, string_types):
            assigned_contexts.add(context_in_database)
        else:
            # There are multiple contexts allowed via this assignment
            assigned_contexts.update(context_in_database)

    return (context in assigned_contexts) or (ALL_ACCESS_CONTEXT in assigned_contexts)


def create_role_auth_claim_for_user(user):
    """
    Create role auth claim for a given user.

    Takes a user, and for each RoleAssignment class specified in config as a
    system wide jwt role associated with that user, creates a list of strings
    denoting the role and context.

    Returns a list.

    This setting is a list of classes whose roles should be added to the
    jwt. The setting should look something like this:

        SYSTEM_WIDE_ROLE_CLASSES = [
            SystemWideConcreteUserRoleAssignment
        ]
    """
    def append_role_auth_claim(role_string, context=None):
        """
        Append the formatted auth claim for a role and context.
        """
        if context:
            contextual_role = '{}:{}'.format(role_string, context)
            role_auth_claim.append(contextual_role)
        else:
            role_auth_claim.append(role_string)

    role_auth_claim = []
    for system_role_loc in settings.SYSTEM_WIDE_ROLE_CLASSES:
        # location can either be a module or a django model
        module_name, func_name = system_role_loc.rsplit('.', 1)
        try:
            # first, assume that this is a plain function
            module = importlib.import_module(module_name)
            role_func = getattr(module, func_name)
        except (ImportError, AttributeError):
            # otherwise, assume that it's a django model
            module = apps.get_model(module_name, func_name)
            role_func = module.get_assignments

        for role_string, context in role_func(user):
            if context:
                if isinstance(context, string_types):
                    append_role_auth_claim(role_string, context)
                else:
                    for item in context:
                        append_role_auth_claim(role_string, item)
            else:
                append_role_auth_claim(role_string)
    return role_auth_claim
