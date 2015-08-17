import copy
import json
import re

from .errors import APIMethodNotAllowedError, BoomiError

DEFAULT_SUPPORTED = {
    "get": True,
    "query": True,
    "put": True,
    "post": True,
    "delete": True,
}

QUERY_OPERATOR_REGEX = re.compile("^(\w+?)(?:__(eq|not|like|gte?|lte?|starts?_with|null|not_null|between))?$")
QUERY_OPERATOR_LOOKUP = {
    "eq": "EQUALS",
    "not": "NOT_EQUALS",
    "like": "LIKE",
    "gt": "GREATER_THAN",
    "gte": "GREATER_THAN_OR_EQUAL",
    "lt": "LESS_THAN",
    "lte": "LESS_THAN_OR_EQUAL",
    "start_with": "STARTS_WITH",
    "starts_with": "STARTS_WITH",
    "null": "IS_NULL",
    "not_null": "IS_NOT_NULL",
    "between": "BETWEEN"
}

class Resource(object):
    """ A base boomi resource. """

    _id_attr = None
    _attributes = tuple()
    _name = "Resource"
    _uri = None

    supported = DEFAULT_SUPPORTED

    @property
    @classmethod
    def __name__(cls):
        return cls.name

    def __init__(self, **kwargs):
        for attr in self._attributes:
            setattr(self, attr, None)

        for key, value in kwargs.iteritems():
            if key in self._attributes:
                setattr(self, key, value)


    @classmethod
    def create_resource(cls, type_, attributes, id_attr="id", **supported_methods):

        _supported = copy.copy(DEFAULT_SUPPORTED)
        _supported.update(supported_methods)

        class SubResource(Resource):
            _uri = type_
            _name = type_
            _id_attr = id_attr
            _attributes = attributes
            supported = _supported

        return SubResource


    @classmethod
    def __https_request(cls, url, method="get", data=None):
        actual_method = method

        # Make sure we're checking capabilities againts real permissions, despite Boomi's silly rest
        # api using POST for everything.
        if "update" in url:
            actual_method = "put"
        elif "query" in url:
            actual_method = "query"

        if not cls.supported.get(actual_method):
            raise APIMethodNotAllowedError(method)

        if data is None:
            data = {}

        return cls._api.https_request(url, method, data)


    def __update_attrs_from_response(self, res):
        res_json = json.loads(res.content)
        for attr in self._attributes:
            setattr(self, attr, res_json.get(attr))


    def serialize(self):
        return {k: getattr(self, k) for k in self._attributes if getattr(self, k) is not None}


    @classmethod
    def get(cls, boomi_id):

        resource = cls()
        res = cls.__https_request(resource.url(boomi_id=boomi_id), method="get")
        resource.__update_attrs_from_response(res)

        return resource


    @classmethod
    def query(cls, join="and", **kwargs):
        expressions = []

        for key, value in kwargs.iteritems():
            if value is not None:
                operator = "EQUALS"
                prop, op = QUERY_OPERATOR_REGEX.match(key).groups()
                if op:
                    operator = QUERY_OPERATOR_LOOKUP[op]

                if not isinstance(value, list):
                    value = [value]

                expressions.append({
                    "argument": value,
                    "operator": operator,
                    "property": prop
                })

        if len(expressions) == 1:
            expressions = expressions[0]
        elif len(expressions) > 1:
            expressions = {
                "operator": join,
                "nestedExpression": expressions
            }

        if expressions:
            q = {"QueryFilter": {"expression": expressions}}
        else:
            q = {}

        res = cls.__https_request("%s/query" % cls.__base_url(), method="post", data=q)
        query_result = json.loads(res.content)
        response = []
        for payload in query_result.get("result", []):
            entity = cls()
            response.append(entity)
            for attr in cls._attributes:
                setattr(entity, attr, payload.get(attr))

        return response


    def save(self, **kwargs):
        url = self.url()

        if getattr(self, self._id_attr) is not None:
            url = "%s/update" % url

        res = self.__https_request(self.url(), method="post", data=self.serialize())
        self.__update_attrs_from_response(res)


    def delete(self, **kwargs):
        if getattr(self, self._id_attr) is None:
            raise BoomiError("Cannot call delete() on object which has not been saved yet.")

        self.__https_request(self.url(), method="delete", data=self.serialze())


    @classmethod
    def __base_url(cls):
        base_url = cls._api.base_url()
        return "%s/%s" % (base_url, cls._uri)


    def url(self, boomi_id=None):
        if getattr(self, self._id_attr) is None and boomi_id is None:
            return self.__base_url()

        base_url = self._api.base_url()
        boomi_id = getattr(self, self._id_attr) if boomi_id is None else boomi_id
        return "%s/%s/%s" % (base_url, self._uri, boomi_id)

