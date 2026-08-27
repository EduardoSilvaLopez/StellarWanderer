class Rock:
    def __init__(self, parent_chunk, id, x, y, z, size):
        self.parent_chunk = parent_chunk
        self.id = id
        self.x = x
        self.y = y
        self.z = z
        self.size = size
