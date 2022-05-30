This test ensures that predicted transfers from blocks are correctly merged 
with existing trip-to-trip transfers using type 4/5.

Block a specifies the order 1a-2a-3a-4a, and series of trip-to-trip transfers
specify the order 2a-3a-4x. The merged result is therefore 1a-2a-3a-4x.
