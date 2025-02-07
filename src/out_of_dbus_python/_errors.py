# Copyright 2016 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Error hierarchy for xformer generator.
"""


class OutOfDPError(Exception):
    """
    Top-level error.
    """


class OutOfDPGenerationError(OutOfDPError):
    """
    Exception raised during generation of a function.
    """


class OutOfDPImpossibleTokenError(OutOfDPGenerationError):
    """
    Exception raised when an impossible token is encountered.
    This should never occur, because the parser should fail.
    """


class OutOfDPRuntimeError(OutOfDPError):
    """
    Exception raised during execution of generated functions.
    """


class OutOfDPUnexpectedValueError(OutOfDPRuntimeError):
    """
    Exception raised when an unexpected value is encountered during a
    transformation.
    """

    def __init__(self, message, value):
        """
        Initializer.

        :param str message: the message
        :param object value: the value encountered
        """
        super().__init__(message)
        self.value = value


class OutOfDPSurprisingError(OutOfDPRuntimeError):
    """
    Exception raised when a surprising error is caught during a transformation.
    Surprising errors can arise due to undocumented or incorrectly documented
    behaviors of dependent libraries or bugs in this library or dependent
    libraries.
    """

    def __init__(self, message, value):  # pragma: no cover
        """
        Initializer.

        :param str message: the message
        :param object value: the value encountered
        """
        super().__init__(message)
        self.value = value


class OutOfDPSignatureError(OutOfDPError):
    """
    Exception raised when a value does not seem to have a valid signature.
    """

    def __init__(self, message, value):
        """
        Initializer.

        :param str message: the message
        :param object value: the problematic putative dbus-python object
        """
        super().__init__(message)
        self.value = value
