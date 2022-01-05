try:
    __import__('google.protobuf')
except ImportError as e:
    raise ImportError("could not import google.protobuf") from e
