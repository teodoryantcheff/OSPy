# import pprint

import cstruct
import pprint


class TStruct(cstruct.CStruct):
    """ For the as_dict method"""
    def as_dict(self):
        """Recursively traverse and return a deep dict"""
        result = {}
        for field in self.__fields__:
            # if hasattr(type(getattr(self, field)), 'as_dict'):
            if isinstance(getattr(self, field), cstruct.CStruct):
                result[field] = getattr(self, field).as_dict()
            elif isinstance(getattr(self, field), list):
                result[field] = [i.as_dict() for i in getattr(self, field)]
            else:
                result[field] = getattr(self, field)
        return result


class rxMetrics_t(TStruct):
    __byte_order__ = cstruct.LITTLE_ENDIAN
    __struct__ = """
        signed char rssi;
        unsigned char lqi;
    """


class connInfo_t(TStruct):
    __byte_order__ = cstruct.LITTLE_ENDIAN
    __struct__ = """
        unsigned char connState;
        unsigned char hops2target;
        unsigned char ackTID;
        unsigned int peerAddr;
        struct rxMetrics_t sigInfo;
        unsigned char portRx;
        unsigned char portTx;
        unsigned char thisLinkID;
    """


class sfClientInfo_t(TStruct):
    __byte_order__ = cstruct.LITTLE_ENDIAN
    __struct__ = """
        unsigned int clientAddr;
        unsigned char lastTID;
    """


class sfInfo_t(TStruct):
    __byte_order__ = cstruct.LITTLE_ENDIAN
    __struct__ = """
        unsigned char         curNumSFClients;
        struct sfClientInfo_t sfClients[4];
    """


class persistentContext_t(TStruct):
    __byte_order__ = cstruct.LITTLE_ENDIAN
    __struct__ = """
        unsigned char structureVersion;
        unsigned char numConnections;
        unsigned char curNextLinkPort;
        unsigned char curMaxReplyPort;
        unsigned char nextLinkID;
        struct sfInfo_t   sSandFContext;
        struct connInfo_t connStruct[49];
    """


if __name__ == '__main__':

    context = persistentContext_t()
    with open('./data/netconf.bin', 'rb') as c:
        context.unpack(c.read())
    d = context.as_dict()

    try:
        import simplejson as json
    except ImportError:
        import json

    pprint.pprint(d, indent=2)
    with open('./data/netconf.json', 'wb') as json_file:
        json.dump(d, json_file, ensure_ascii=True, sort_keys=True)
    print 'done'


    # print json.dumps(d, indent=2, sort_keys=True)
    # pprint.pprint(context.__dict__, indent=2)