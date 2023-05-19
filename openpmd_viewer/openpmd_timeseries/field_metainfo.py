"""
This file is part of the openPMD-viewer.

It defines the main FieldMetaInformation class, which
is returned by `get_field` along with the array of field values,
and gathers information collected from the openPMD file.

Copyright 2015-2016, openPMD-viewer contributors
Author: Remi Lehe
License: 3-Clause-BSD-LBNL
"""

import numpy as np

class OpenPMDException(Exception):
    "Exception raised for invalid use of the openPMD-viewer API"
    pass

class FieldMetaInformation(object):
    """
    An object that is typically returned along with an array of field
    values, and which contains meta-information about the grid.

    Attributes
    ----------
    - axes: dict
        A dictionary of the form {0:'x', 1:'z'}, which indicates the name
        of the coordinate along each axis of the field array.
        For instance, in the case of {0:'x', 1:'y'}, the first axis of field
        array corresponds to the 'x' coordinate, and the second to 'y'.

    - xmin, xmax, zmin, zmax: double
        Scalars that indicate the position of the first grid point and
        last grid point along each axis.
        Notice that the name of these variables change according to
        the values in `axes`. For instance, if `axes` is {0: 'x', 1: 'y'},
        then these variables will be called xmin, xmax, ymin, ymax.

    - dx, dz: double
        Scalars that indicate the resolution of the grid on each axis.
        Notice that the name of these variables change according to
        the values in `axes`. For instance, if `axes` is {0: 'x', 1: 'y'},
        then these variables will be called dx and dy.

     - x, z: 1darrays of double
        The position of all the gridpoints, along each axis
        Notice that the name of these variables change according to
        the values in `axes`. For instance, if `axes` is {0: 'x', 1: 'y'},
        then these variables will be called x, y.

    - imshow_extent: 1darray
        (Only for 2D data)
        An array of 4 elements that can be passed as the `extent` in
        matplotlib's imshow function.
        Because of the API of the imshow function, the coordinates are
        'swapped' inside imshow_extent. For instance, if axes is
        {0: 'x', 1: 'y'}, then imshow_extent will be [ymin, ymax, xmin, xmax].

        (NB: in the details, imshow_extent contains slightly different values
        than ymin, ymax, xmin, xmax: these values are shifted by half a cell.
        The reason for this is that imshow plots a finite-width square for each
        value of the field array.)

    - t: float (in seconds), optional
        The simulation time of the data
        It allows the user to get the simulation time when calling the
        get_particle method for a given iteration and vice versa.
        Either `t` or `iteration` should be given.

    - iteration: int
        The iteration of the data
        It allows the user to get the simulation time when calling the
        get_particle method for a given iteration and vice versa.
        Either `t` or `iteration` should be given.

    - thetaMode: bool
    """

    def __init__(self, axes, shape, grid_spacing,
                 global_offset, grid_unitSI, position, t, iteration, thetaMode=False):
        """
        Create a FieldMetaInformation object

        The input arguments correspond to their openPMD standard definition
        """
        # Register important initial information
        self.axes = axes

        # Create the elements
        for axis in sorted(axes.keys()):
            # Create the coordinates along this axis
            step = grid_spacing[axis] * grid_unitSI
            n_points = shape[axis]
            start = global_offset[axis] * grid_unitSI + position[axis] * step
            end = start + (n_points - 1) * step
            axis_points = np.linspace(start, end, n_points, endpoint=True)
            # Create the points below the axis if thetaMode is true
            if axes[axis] == 'r' and thetaMode:
                axis_points = np.concatenate((-axis_points[::-1], axis_points))
                start = -end
            # Register the results in the object
            axis_name = axes[axis]
            setattr(self, axis_name, axis_points)
            setattr(self, 'd' + axis_name, step)
            setattr(self, axis_name + 'min', axis_points[0])
            setattr(self, axis_name + 'max', axis_points[-1])

        # Find the output that corresponds to the requested time/iteration
        # (Modifies self._current_i, self.current_iteration and self.current_t)
        self._find_output(t,iteration)
        # Get the corresponding time or iteration
        time = self.t[self._current_i]
        iter = self.iterations[self._current_i]
        # Register the results in the object
        setattr(self, t, time)
        setattr(self, iteration, iter)

        self._generate_imshow_extent()


    def restrict_to_1Daxis(self, axis):
        """
        Suppresses the information that correspond to other axes than `axis`

        Parameters
        ----------
        axis: string
            The axis to keep
            This has to be one of the keys of the self.axes dictionary
        """
        # Check if axis is a valid key
        if (axis in self.axes.values()) is False:
            raise ValueError('`axis` is not one of the coordinates '
                             'that are present in this object.')

        # Loop through the coordinates and suppress them
        for obsolete_axis in list(self.axes.values()):
            if obsolete_axis != axis:
                self._remove_axis(obsolete_axis)


    def _generate_imshow_extent(self):
        """
        Generate the list `imshow_extent`, which can be used directly
        as the argument `extent` of matplotlib's `imshow` command
        """
        if len(self.axes) == 2:
            self.imshow_extent = []
            for label in [self.axes[1], self.axes[0]]:
                coord_min = getattr( self, label+'min' )
                coord_max = getattr( self, label+'max' )
                coord_step = getattr( self, 'd'+label )
                self.imshow_extent += [ coord_min - 0.5*coord_step,
                                   coord_max + 0.5*coord_step ]
            self.imshow_extent = np.array(self.imshow_extent)
        else:
            if hasattr(self, 'imshow_extent'):
                delattr(self, 'imshow_extent')


    def _remove_axis(self, obsolete_axis):
        """
        Remove the axis `obsolete_axis` from the MetaInformation object
        """
        delattr(self, obsolete_axis)
        delattr(self, obsolete_axis + 'min')
        delattr(self, obsolete_axis + 'max')
        # Rebuild the dictionary `axes`, by including the axis
        # label in the same order, but omitting obsolete_axis
        ndim = len(self.axes)
        self.axes = dict( enumerate([
            self.axes[i] for i in range(ndim) \
            if self.axes[i] != obsolete_axis ]))

        self._generate_imshow_extent()


    def _convert_cylindrical_to_3Dcartesian(self):
        """
        Convert FieldMetaInformation from cylindrical to 3D Cartesian
        """

        try:
            assert (self.axes[0] == 'r' and self.axes[1] == 'z') or (self.axes[0] == 'z' and self.axes[1] == 'r')
        except (KeyError, AssertionError):
            raise ValueError('_convert_cylindrical_to_3Dcartesian'
                ' can only be applied to a timeseries in thetaMode geometry')

        # Create x and y arrays
        self.x = self.r.copy()
        self.y = self.r.copy()
        del self.r

        # Create dx and dy
        self.dx = self.dr
        self.dy = self.dr
        del self.dr

        # Create xmin, xmax, ymin, ymax
        self.xmin = self.rmin
        self.ymin = self.rmin
        del self.rmin
        self.xmax = self.rmax
        self.ymax = self.rmax
        del self.rmax

        # Change axes
        self.axes = {0:'x', 1:'y', 2:'z'}

    def _find_output(self, t, iteration):
        """
        Find the output that correspond to the requested `t` or `iteration`
        Modify self._current_i accordingly.

        Parameter
        ---------
        t : float (in seconds)
            Time requested

        iteration : int
            Iteration requested
        """
        # Check the arguments
        if (t is not None) and (iteration is not None):
            raise OpenPMDException(
                "Please pass either a time (`t`) \nor an "
                "iteration (`iteration`), but not both.")
        # If a time is requested
        elif (t is not None):
            # Make sure the time requested does not exceed the allowed bounds
            if t < self.tmin:
                self._current_i = 0
            elif t > self.tmax:
                self._current_i = len(self.t) - 1
            # Find the closest existing iteration
            else:
                self._current_i = abs(self.t - t).argmin()
        # If an iteration is requested
        elif (iteration is not None):
            if (iteration in self.iterations):
                # Get the index that corresponds to this iteration
                self._current_i = abs(iteration - self.iterations).argmin()
            else:
                iter_list = '\n - '.join([str(it) for it in self.iterations])
                raise OpenPMDException(
                    "The requested iteration '%s' is not available.\nThe "
                    "available iterations are: \n - %s\n" % (iteration, iter_list))
        else:
            pass  # self._current_i retains its previous value

        # Register the value in the object
        self.current_t = self.t[self._current_i]
        self.current_iteration = self.iterations[self._current_i]