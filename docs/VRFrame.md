# The `VRFrame` class

A `Frame` object has the following core member variables:

* `fields`: a dictionary mapping field names to a single `FAMatch` object 
   or a list of them

If there are no `FAMatch`es for a given field name, the field name will not 
be present in the dictionary.
