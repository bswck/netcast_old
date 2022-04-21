from netcast.model import Model


class IdentifiableModel(Model, skip_subclass_hook=True):
    _id_field = "id"

