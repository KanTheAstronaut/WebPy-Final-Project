from typing import Self, get_type_hints

class MongoObject():
    # convert to mongo safe format
    # accept dict as an argument to override self.__dict__
    def MongoSafeObject(self, dict: dict = None) -> dict:
        dic = (self.__dict__ if dict is None else dict).copy() # must use .copy or else we would start directly modifying the object that we are trying to convert
        if (dic.get('id', -1) != -1): # if the object contains an id
            del dic['id'] # delete it (from the copy)
           
        for key, value in dic.items():
            if isinstance(value, MongoObject):
                dic[key] = value.MongoSafeObject()
            elif isinstance(value, list) and all(issubclass(i, MongoObject) for i in value):
                dic[key] = [i.MongoSafeObject() for i in value]
        return dic
    
    # convert mongo document back to a class instance 
    @classmethod
    def convertBack(cls, dic: dict) -> Self:
        if "_id" in dic: # if the mongo document has an id
            dic['id'] = str(dic['_id']) # convert the ObjectID _id from mongodb to a string id
            del dic['_id'] # delete the mongodb formatted id
        
        # get all of the types of the arguments in the cls constructor (init)
        initiatorHints = get_type_hints(cls.__init__)

        for key, value in dic.items():
            # if something is a dictionary and matches the name of an argument in the constructor (and also inherits MongoObject)
            if (isinstance(value, dict)) and initiatorHints.get(key) and issubclass(initiatorHints[key], MongoObject):
                # convert the nested object back from a dictionary
                dic[key] = initiatorHints[key].convertBack(dic[key])
                # without that we wouldn't be able to convert statistics (class & property in User) when rereading it from mongodb back to an instance
                # of the statistics class
        return cls(**dic) # instantiate the current class with all of the values from the dictionary as the paramters (this will only work if the __init__'s args have matching names)
