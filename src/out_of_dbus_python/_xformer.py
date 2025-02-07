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
Transforming Python dbus types to Python basic types.
"""

# isort: STDLIB
import functools

# isort: THIRDPARTY
import dbus

# isort: FIRSTPARTY
from dbus_signature_pyparsing import Parser

from ._errors import (
    OutOfDPError,
    OutOfDPImpossibleTokenError,
    OutOfDPSurprisingError,
    OutOfDPUnexpectedValueError,
)


def _wrapper(func):
    """
    Wraps a generated function so that it catches all unexpected errors and
    raises OutOfDPSurprisingErrors.

    :param func: the transforming function
    """

    @functools.wraps(func)
    def the_func(expr, *, variant=0):
        """
        The actual function.

        :param object expr: the expression to be xformed to dbus-python types
        :param int variant: the variant level of the transformed object
        """
        try:
            return func(expr, variant=variant)
        # Allow KeyboardInterrupt error to be propagated
        except KeyboardInterrupt as err:  # pragma: no cover
            raise err
        except OutOfDPError as err:
            raise err
        except BaseException as err:  # pragma: no cover
            raise OutOfDPSurprisingError(
                "encountered a surprising error while transforming some expression",
                expr,
            ) from err

    return the_func


class _FromDbusXformer(Parser):
    """
    Class which extends a Parser to yield a function that yields
    a function that transforms a value in dbus-python types to a correct value
    using base Python types.
    """

    # pylint: disable=too-few-public-methods

    def _handle_variant(self):
        """
        Generate the correct function for a variant signature.

        :returns: function that returns an appropriate value
        :rtype: ((str * object) or list)-> object
        """

        def the_func(a_tuple, *, variant=0):
            """
            Function for generating a variant value from a tuple.

            :param a_tuple: the parts of the variant
            :type a_tuple: (str * object) or list
            :param int variant: object's variant index
            :returns: a value of the correct type
            :rtype: object
            """
            try:
                (signature, an_obj) = a_tuple
                (func, sig) = self.COMPLETE.parseString(signature)[0]
            # Allow KeyboardInterrupt error to be propagated
            except KeyboardInterrupt as err:  # pragma: no cover
                raise err
            except BaseException as err:
                raise OutOfDPUnexpectedValueError(
                    "inappropriate argument or signature for variant type", a_tuple
                ) from err
            assert sig == signature
            return func(an_obj, variant=variant + 1)

        return (the_func, "v")

    @staticmethod
    def _handle_array(toks):
        """
        Generate the correct function for an array signature.

        :param toks: the list of parsed tokens
        :returns: function that returns an Array or Dictionary value
        :rtype: ((or list dict) -> ((or Array Dictionary) * int)) * str
        """

        if len(toks) == 5 and toks[1] == "{" and toks[4] == "}":
            subtree = toks[2:4]
            signature = "".join(s for (_, s) in subtree)
            [key_func, value_func] = [f for (f, _) in subtree]

            def the_dict_func(a_dict, *, _variant=0):
                """
                Function for extracting a dict from a Dictionary.

                :param a_dict: the dictionary to transform
                :type a_dict: Dictionary
                :param int variant: variant level

                :returns: a dbus dictionary of transformed values
                :rtype: Dictionary
                """
                return {key_func(x): value_func(y) for (x, y) in a_dict.items()}

            return (the_dict_func, "a{" + signature + "}")

        if len(toks) == 2:
            (func, sig) = toks[1]

            def the_array_func(a_list, *, _variant=0):
                """
                Function for generating an Array from a list.

                :param a_list: the list to transform
                :type a_list: list of `a
                :param int variant: variant level of the value
                :returns: a dbus Array of transformed values
                :rtype: Array
                """
                if not isinstance(a_list, dbus.types.Array):
                    raise OutOfDPUnexpectedValueError(
                        f"expected an Array but found something else: {a_list}",
                        a_list,
                    )
                return [func(x) for x in a_list]

            return (the_array_func, "a" + sig)

        # This should be impossible, because a parser error is raised on
        # an unexpected token before the handler is invoked.
        raise OutOfDPImpossibleTokenError(
            "Encountered unexpected tokens in the token stream"
        )  # pragma: no cover

    @staticmethod
    def _handle_struct(toks):
        """
        Generate the correct function for a struct signature.

        :param toks: the list of parsed tokens
        :returns: function that returns an Array or Dictionary value
        :rtype: ((list or tuple) -> (Struct * int)) * str
        """
        subtrees = toks[1:-1]
        signature = "".join(s for (_, s) in subtrees)
        funcs = [f for (f, _) in subtrees]

        def the_func(a_struct, *, _variant=0):
            """
            Function for generating a tuple from a struct.

            :param a_struct: the struct to transform
            :type a_struct: Struct
            :param int variant: variant index
            :returns: a dbus Struct of transformed values
            :rtype: tuple
            :raises OutOfDPRuntimeError:
            """
            if not isinstance(a_struct, dbus.types.Struct):
                raise OutOfDPUnexpectedValueError(
                    f"expected a simple sequence for the fields of a struct "
                    f"but found something else: {a_struct}",
                    a_struct,
                )
            if len(a_struct) != len(funcs):
                raise OutOfDPUnexpectedValueError(
                    f"expected {len(funcs)} elements for a struct, "
                    f"but found {len(a_struct)}",
                    a_struct,
                )
            return tuple(f(x) for (f, x) in zip(funcs, a_struct))

        return (the_func, "(" + signature + ")")

    @staticmethod
    def _handle_base_case(klass, symbol):
        """
        Handle a base case.

        :param type klass: the class constructor
        :param str symbol: the type code
        """

        def the_func(value, *, _variant=0):
            """
            Base case.

            :param int variant: variant level for this object
            :returns: a translated Python object
            :rtype: Python object
            """
            try:
                return klass(value)
            # Allow KeyboardInterrupt error to be propagated
            except KeyboardInterrupt as err:  # pragma: no cover
                raise err
            except BaseException as err:
                raise OutOfDPUnexpectedValueError(
                    "inappropriate value passed to dbus-python constructor", value
                ) from err

        return lambda: (the_func, symbol)

    def __init__(self):
        super().__init__()

        self.BYTE.setParseAction(_FromDbusXformer._handle_base_case(int, "y"))
        self.BOOLEAN.setParseAction(_FromDbusXformer._handle_base_case(bool, "b"))
        self.INT16.setParseAction(_FromDbusXformer._handle_base_case(int, "n"))
        self.UINT16.setParseAction(_FromDbusXformer._handle_base_case(int, "q"))
        self.INT32.setParseAction(_FromDbusXformer._handle_base_case(int, "i"))
        self.UINT32.setParseAction(_FromDbusXformer._handle_base_case(int, "u"))
        self.INT64.setParseAction(_FromDbusXformer._handle_base_case(int, "x"))
        self.UINT64.setParseAction(_FromDbusXformer._handle_base_case(int, "t"))
        self.DOUBLE.setParseAction(_FromDbusXformer._handle_base_case(float, "d"))
        self.UNIX_FD.setParseAction(_FromDbusXformer._handle_base_case(int, "h"))
        self.STRING.setParseAction(_FromDbusXformer._handle_base_case(str, "s"))
        self.OBJECT_PATH.setParseAction(_FromDbusXformer._handle_base_case(str, "o"))
        self.SIGNATURE.setParseAction(_FromDbusXformer._handle_base_case(str, "g"))

        self.VARIANT.setParseAction(self._handle_variant)

        self.ARRAY.setParseAction(  # pyright: ignore [ reportOptionalMemberAccess ]
            _FromDbusXformer._handle_array
        )

        self.STRUCT.setParseAction(  # pyright: ignore [ reportOptionalMemberAccess ]
            _FromDbusXformer._handle_struct
        )


_XFORMER = _FromDbusXformer()


def xformers(sig):
    """
    Get the list of xformer functions for the given signature.

    :param str sig: a signature
    :returns: a list of xformer functions for the given signature.
    :rtype: list of tuple of a function * str
    """
    return [
        (_wrapper(f), l) for (f, l) in _XFORMER.PARSER.parseString(sig, parseAll=True)
    ]


def xformer(signature):
    """
    Returns a transformer function for the given signature.

    :param str signature: a dbus signature
    :returns: a function to transform a list of objects to inhabit the signature
    :rtype: (list of object) -> (list of object)
    """

    funcs = [f for (f, _) in xformers(signature)]

    def the_func(objects):
        """
        Returns the a list of objects, transformed.

        :param objects: a list of objects
        :type objects: list of object

        :returns: transformed objects
        :rtype: list of object (in dbus types)
        """
        if len(objects) != len(funcs):
            raise OutOfDPUnexpectedValueError(
                f"expected {len(funcs)} items to transform but found {len(objects)}",
                objects,
            )
        return [f(a) for (f, a) in zip(funcs, objects)]

    return the_func
