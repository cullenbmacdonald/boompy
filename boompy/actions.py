import functools
import json
import time

import boompy
from .base_api import API
from .errors import UnauthorizedError, BoomiError

PROVISION_FIELDS = ["name", "street", "city", "stateCode", "zipCode",
                      "countryCode", "status", "product"]

def getAssignableRoles():
    """ Returns a list of assignable Role objects. """
    results = []
    res = API().https_request("%s/getAssignableRoles" % API().base_url(), "get", {})

    for role in json.loads(res.content).get("Role"):
        results.append(boompy.Role(**role))

    return results

def executeProcess(process_id, atom_id):
    data = {"processId": process_id, "atomId": atom_id}
    API().https_request("%s/executeProcess" % API().base_url(), "post", data)

def provisionPartnerCustomerAccount(data=None):
    """
    Method that will use the Boomi action to provision a new account for
    the data passed in, if the required field(s) are missing from the dictionary
    then a Boomi Error is raised
    """

    if data is None:
        data = {}

    # It takes about a minute for this process to complete
    base_url = "%s/AccountProvision" % API().base_url(partner=True)

    data_fields = [key for key in data]
    missing_fields = set(PROVISION_FIELDS) - set(data_fields)

    if len(missing_fields) == 0:
        res = API().https_request("%s/execute" % base_url, "post", data)
        results = json.loads(res.content)

        while results.get("status") == "PENDING":
            time.sleep(2)
            result = API().https_request("%s/%s" % (base_url, results.get("id")), "get", {})
            results = json.loads(result.content)
        if results.get("status") != "COMPLETED":
            raise BoomiError("failed setting up account")
        else:
            return results
    else:
        raise BoomiError(("incomplete provison data provided, you are missing "
                          "the following fields: ") + str(list(missing_fields)))
