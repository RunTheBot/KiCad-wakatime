from kipy import KiCad
from kipy.proto.common.types import DocumentType


if __name__=='__main__':
    try:
        kicad = KiCad()
        print(f"Connected to KiCad {kicad.get_version()}")
        print(f"Project: {kicad.get_open_documents(DocumentType.DOCTYPE_PCB)}")
    except BaseException as e:
        print(f"Not connected to KiCad: {e}")
