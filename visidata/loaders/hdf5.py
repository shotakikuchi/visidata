from visidata import *

class SheetH5Obj(Sheet):
    'Support sheets in HDF5 format.'
    commands = [
        Command(ENTER, 'vd.push(SheetH5Obj(joinSheetnames(name,cursorRow.name), cursorRow))', 'open this group or dataset'),
        Command('A', 'vd.push(SheetDict(cursorRow.name + "_attrs", cursorRow.attrs))', 'open metadata sheet for this object')
    ]

    def reload(self):
        import h5py
        if isinstance(self.source, h5py.Group):
            self.columns = [
                Column(self.source.name, str, lambda r: r.name.split('/')[-1]),
                Column('type', str, lambda r: type(r).__name__),
                Column('nItems', int, lambda r: len(r)),
            ]
            self.rows = [ self.source[objname] for objname in self.source.keys() ]
        elif isinstance(self.source, h5py.Dataset):
            if len(self.source.shape) == 1:
                self.columns = [ColumnItem(colname, colname) for colname in self.source.dtype.names or [0]]
                self.rows = self.source[:]  # copy
            elif len(self.source.shape) == 2:  # matrix
                self.columns = ArrayColumns(self.source.shape[1])
                self.rows = self.source[:]  # copy
            else:
                status('too many dimensions in shape %s' % str(self.source.shape))
        else:
            status('unknown h5 object type %s' % type(self.source))

class open_hdf5(SheetH5Obj):
    def __init__(self, p):
        import h5py
        super().__init__(p.name, h5py.File(str(p), 'r'))

open_h5 = open_hdf5
