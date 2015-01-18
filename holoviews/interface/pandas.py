"""
The interface subpackage provides View and Plot types to wrap external
objects with. Currently only a Pandas compatibility wrapper is
provided, which allows integrating Pandas DataFrames within the
holoviews compositioning and animation framework. Additionally, it
provides methods to apply operations to the underlying data and
convert it to standard holoviews View types.
"""

from __future__ import absolute_import

from collections import OrderedDict

import numpy as np

try:
    import pandas as pd
except:
    pd = None

import param

from ..core import Dimension, NdMapping, View, Layer, Overlay, ViewMap, GridLayout, Grid
from ..core.options import options, PlotOpts
from ..view import HeatMap, Table, Curve, Scatter, Bars, Points, VectorField


class DataFrameView(Layer):
    """
    DataFrameView provides a convenient compatibility wrapper around
    Pandas DataFrames. It provides several core functions:

        * Allows integrating several Pandas plot types with the
          holoviews plotting system (includes plot, boxplot, histogram
          and scatter_matrix).

        * Provides several convenient wrapper methods to apply
          DataFrame methods and slice data. This includes:

              1) The apply method, which takes the DataFrame method to
                 be applied as the first argument and passes any
                 supplied args or kwargs along.

              2) The select and __getitem__ method which allow for
                 selecting and slicing the data using NdMapping.
    """

    plot_type = param.ObjectSelector(default=None, 
                                     objects=['plot', 'boxplot',
                                              'hist', 'scatter_matrix',
                                              'autocorrelation_plot',
                                              None],
                                     doc="""Selects which Pandas plot type to use,
                                            when visualizing the View.""")

    x = param.String(doc="""Dimension to visualize along the x-axis.""")

    x2 = param.String(doc="""Dimension to visualize along a second
                             dependent axis.""")

    y = param.String(doc="""Dimension to visualize along the y-axis.""")

    value = param.String(default='DFrame')

    value_dimensions = param.List(doc="DataFrameView has no value dimension.")

    def __init__(self, data, index_dimensions=None, **params):
        if pd is None:
            raise Exception("Pandas is required for the Pandas interface.")
        if not isinstance(data, pd.DataFrame):
            raise Exception('DataFrame View type requires Pandas dataframe as data.')
        if index_dimensions is None:
            dims = list(data.columns)
        else:
            dims = ['' for i in range(len(data.columns))]
            for dim in index_dimensions:
                dim_name = dim.name if isinstance(dim, Dimension) else dim
                if dim_name in data.columns:
                    dims[list(data.columns).index(dim_name)] = dim

        self._xlim = None
        self._ylim = None
        View.__init__(self, data, index_dimensions=dims, **params)
        self.data.columns = self._cached['index_names']


    def __getitem__(self, key):
        """
        Allows slicing and selecting along the DataFrameView dimensions.
        """
        if key is ():
            return self
        else:
            if len(key) <= self.ndims:
                return self.select(**dict(zip(self._cached['index_names'], key)))
            else:
                raise Exception('Selection contains %d dimensions, DataFrameView '
                                'only has %d index dimensions.' % (self.ndims, len(key)))


    def select(self, **select):
        """
        Allows slice and select individual values along the DataFrameView
        dimensions. Supply the dimensions and values or slices as
        keyword arguments.
        """
        df = self.data
        for dim, k in select.items():
            if isinstance(k, slice):
                df = df[(k.start < df[dim]) & (df[dim] < k.stop)]
            else:
                df = df[df[dim] == k]
        return self.clone(df)


    def dimension_values(self, dim):
        return np.array(self.data[dim])


    def apply(self, name, *args, **kwargs):
        """
        Applies the Pandas dframe method corresponding to the supplied
        name with the supplied args and kwargs.
        """
        return self.clone(getattr(self.data, name)(*args, **kwargs))


    def dframe(self):
        """
        Returns a copy of the internal dframe.
        """
        return self.data.copy()


    def _split_dimensions(self, dimensions, ndmapping_type=NdMapping):
        invalid_dims = list(set(dimensions) - set(self._cached['index_names']))
        if invalid_dims:
            raise Exception('Following dimensions could not be found %s.'
                            % invalid_dims)

        index_dims = [self.get_dimension(d) for d in dimensions]
        ndmapping = ndmapping_type(None, index_dimensions=index_dims)
        view_dims = set(self._cached['index_names']) - set(dimensions)
        view_dims = [self.get_dimension(d) for d in view_dims]
        for k, v in self.data.groupby(dimensions):
            ndmapping[k] = self.clone(v.drop(dimensions, axis=1),
                                      index_dimensions=view_dims)
        return ndmapping


    def overlay(self, dimensions):
        return self._split_dimensions(dimensions, Overlay)


    def layout(self, dimensions=[], cols=4):
        return self._split_dimensions(dimensions, GridLayout).cols(4)


    def grid(self, dimensions):
        """
        Splits the supplied the dimensions out into a Grid.
        """
        if len(dimensions) > 2:
            raise Exception('Grids hold a maximum of two dimensions.')
        return self._split_dimensions(dimensions, GridLayout)


    def viewmap(self, index_dimensions=[]):
        """
        Splits the supplied dimensions out into a ViewMap.
        """
        return self._split_dimensions(index_dimensions, ViewMap)

    @property
    def xlabel(self):
        return self.x

    @property
    def ylabel(self):
        return self.y

    @property
    def xlim(self):
        if self._xlim:
            return self._xlim
        if self.x:
            xdata = self.data[self.x]
            return min(xdata), max(xdata)
        else:
            return None

    @property
    def ylim(self):
        if self._ylim:
            return self._ylim
        elif self.y:
            ydata = self.data[self.y]
            return min(ydata), max(ydata)
        else:
            return None



class DFrame(DataFrameView):
    """
    DFrame is a DataFrameView type, which additionally provides
    methods to convert Pandas DataFrames to different View types,
    currently including Tables and HeatMaps.

    The View conversion methods all share a common signature:

      * The value dimension (string).
      * The index dimensions (list of strings).
      * An optional reduce_fn.
      * Optional map_dims (list of strings).
    """

    def bars(self, *args, **kwargs):
        return self.table(*args, **dict(view_type=Bars, **kwargs))

    def curve(self, *args, **kwargs):
        return self.table(*args, **dict(view_type=Curve, **kwargs))

    def heatmap(self, *args, **kwargs):
        return self.table(*args, **dict(view_type=HeatMap, **kwargs))

    def points(self, *args, **kwargs):
        return self.table(*args, **dict(view_type=Points, **kwargs))

    def scatter(self, *args, **kwargs):
        return self.table(*args, **dict(view_type=Scatter, **kwargs))

    def vectorfield(self, *args, **kwargs):
        return self.table(*args, **dict(view_type=VectorField, **kwargs))

    def table(self, value_dims, view_dims, reduce_fn=None, map_dims=[], view_type=None, **kwargs):
        if map_dims:
            map_groups = self.data.groupby(map_dims)
            vm_dims = map_dims
        else:
            map_groups = [(0, self.data)]
            vm_dims = ['None']

        vmap = ViewMap(index_dimensions=vm_dims)
        vdims = [self.get_dimension(dim) for dim in view_dims]
        valdims = [self.get_dimension(d) for d in value_dims]
        for map_key, group in map_groups:
            table_data = OrderedDict()
            for k, v in group.groupby(view_dims):
                data = np.vstack(np.array(v[d]) for d in value_dims)
                data = reduce_fn(data, axis=0) if reduce_fn else data[0, :]
                table_data[k] = reduce_fn(data, axis=0) if reduce_fn else data[0]
            view = Table(table_data, index_dimensions=vdims,
                         value_dimensions=valdims, value=self.value)
            vmap[map_key] = view_type(view, **kwargs) if view_type else view
        return vmap if map_dims else vmap.last


options.DFrameView = PlotOpts()
