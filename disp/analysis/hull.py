"""
Tools for constructing convex hulls
"""
import numpy as np
import plotly.graph_objects as go
from pymatgen.analysis.phase_diagram import PDPlotter

# pylint: disable=invalid-name, too-many-locals


class PlotlyPDPlotter(PDPlotter):
    """
    An extension of the PDPlotter for plotting phase diagram with `plotly`

    This may only work with the old pymatgen version that does not have the native plotly
    backend support
    """
    @property
    def pd_plot_data_ternary(self):
        """
        Get the plot data for native ternary plot.

        Returns:
            (lines, stable_entries, unstable_entries):
            Same as pd_plot_data, but in proper ternary coordinates
        """
        assert self._dim == 3, 'Cannot get data for ternary plot - the system is not ternary'
        pd = self._pd
        entries = pd.qhull_entries

        def recover_a(old_data):
            """Recover the a coordinates"""
            old_shape = old_data.shape
            data = np.zeros(
                (old_shape[0], old_shape[1] + 1))  # Convert to numpy format
            data[:, 1:] = old_data  # Assign the old data
            data[:, 0] = 1 - (old_data[:, 0] + old_data[:, 1]
                              )  # re-obtain the fraction of the first element
            return data

        data = recover_a(pd.qhull_data)
        lines = []
        stable_entries = {}
        for line in self.lines:
            entry1 = entries[line[0]]
            entry2 = entries[line[1]]
            # The coordinates are the atomic fractions of the second and the third elements
            # and we need to recovery the first one
            coord = data[line, :3]
            lines.append(coord)
            # Record the terminal coorindates - these are the stable entries
            stable_entries[tuple(coord[0])] = entry1
            stable_entries[tuple(coord[1])] = entry2

        all_entries = pd.all_entries
        all_data = recover_a(pd.all_entries_hulldata)
        unstable_entries = dict()
        stable = pd.stable_entries
        for i, entry in enumerate(all_entries):
            entry = all_entries[i]
            if entry not in stable:
                coord = all_data[i, :3]
                unstable_entries[entry] = coord

        return lines, stable_entries, unstable_entries

    def _get_3d_ternary_plot(self):  # pylint: disable=too-many-statements
        """
        Obtain a 3D ternary plot with all phases, stable and unstable...
        """
        fig = go.Figure()

        # This is not a ternary plot, but a 3d plot of the ternary space...
        lines, labels, unstable = self.pd_plot_data
        pd = self._pd

        # Plot the lines
        x_list, y_list, z_list = [], [], []
        for x, y in lines:
            x_list.extend(tuple(x) + (None, ))
            y_list.extend(tuple(y) + (None, ))

            entry1 = labels[(x[0], y[0])]
            entry2 = labels[(x[1], y[1])]
            form_eng1 = pd.get_form_energy_per_atom(entry1)
            form_eng2 = pd.get_form_energy_per_atom(entry2)
            z_list.extend((form_eng1, form_eng2, None))

        # Plot the facet
        fig.add_scatter3d(x=x_list,
                          y=y_list,
                          z=z_list,
                          mode='lines',
                          hoverinfo='none')

        elems = pd.elements

        # Find what types of entries do we have
        all_types = [entry_type(entry, 'Default') for entry in pd.all_entries]
        all_types = sorted(list(set(all_types)))

        # Plot stable phases
        all_stable_names = set()
        for etype in all_types:
            stable_coords = []
            stable_text = []
            form_engs = []
            for coords in sorted(labels.keys(), key=lambda x: -x[1]):
                entry = labels[coords]
                if entry_type(entry, 'Default') != etype:
                    continue
                label = entry.name
                stable_coords.append(coords)
                stable_text.append(label)
                all_stable_names.add(label)
                # Formation energies are the z axis
                form_engs.append(pd.get_form_energy_per_atom(entry))

            if not stable_coords:
                continue
            x, y = list(zip(*stable_coords))
            fig.add_scatter3d(x=x,
                              y=y,
                              z=form_engs,
                              text=stable_text,
                              name=f'Stable ({etype})',
                              mode='markers+text',
                              marker_size=5)
        # Plot the unstable phases
        if self.show_unstable:
            for etype in all_types:
                unstable_coords = []
                unstable_text = []
                unstable_name = []
                nsamples = len(unstable)
                form_engs = []
                for entry, coords in unstable.items():
                    # Only plot this type, and skip those that are stable
                    if entry_type(entry, 'Unstable') != etype:
                        continue
                    ehull = pd.get_e_above_hull(entry)
                    if ehull > self.show_unstable:
                        continue
                    unstable_coords.append(coords)
                    unstable_text.append(entry.name)
                    unstable_name.append(entry_name(entry))
                    form_engs.append(pd.get_form_energy_per_atom(entry))
                if not unstable_coords:
                    continue
                x, y = list(zip(*unstable_coords))
                fig.add_scatter3d(
                    x=x,
                    y=y,
                    z=form_engs,
                    text=unstable_text,
                    customdata=np.array([unstable_name]).T,
                    name=f'Unstable ({etype})',
                    mode='markers',
                    hovertemplate='%{text} - %{customdata[0]}',
                    marker_size=2,
                )

        pname = '-'.join(map(lambda x: x.name, elems))
        fig.update_layout({
            'title': f'Ternary plot for {pname}',
            'autosize': False,
            'height': 600,
            'width': 800,
        })
        return fig

    def _get_2d_ternary_plot(self):  # pylint: disable=too-many-statement,too-many-branches
        """
        Obtain the 2D ternary plot
        """
        pd = self._pd

        # Plot the lines
        lines, labels, unstable = self.pd_plot_data_ternary
        fig = go.Figure()

        # Construct a list of abc coordinates, but separator as they are segments
        a_list, b_list, c_list = [], [], []
        for startfinish in lines:
            a, b, c = list(zip(*startfinish))
            a_list.extend(a + (None, ))
            b_list.extend(b + (None, ))
            c_list.extend(c + (None, ))

        # Plot the facet
        fig.add_scatterternary(a=a_list,
                               b=b_list,
                               c=c_list,
                               mode='lines',
                               hoverinfo='none')

        elems = pd.elements

        # Find what types of entries do we have
        all_types = [entry_type(entry, 'Default') for entry in pd.all_entries]
        all_types = sorted(list(set(all_types)))

        # plot the stable phases for each type
        all_stable_names = set()
        for etype in all_types:
            stable_coords = []
            stable_text = []
            stable_name = []
            for coords in sorted(labels.keys(), key=lambda x: -x[1]):
                entry = labels[coords]
                if entry_type(entry, 'Default') != etype:
                    continue
                label = entry.name
                stable_coords.append(coords)
                stable_text.append(label)
                all_stable_names.add(label)
                stable_name.append(entry_name(entry))
            a, b, c = list(zip(*stable_coords))
            aname, bname, cname = map(lambda x: x.name, elems)
            fig.add_scatterternary(
                a=a,
                b=b,
                c=c,
                text=stable_text,
                marker_symbol='circle',
                name=f'Stable ({etype})',
                mode='markers+text',
                customdata=np.array([stable_name]).T,
                hovertemplate=
                f'{aname}: %{{a:.2f}} {bname}: %{{b:.2f}} {cname}: %{{c:.2f}}<br>name: %{{customdata[0]}}',
                cliponaxis=False)

        # Plot the unstable phases
        if self.show_unstable:
            # Screen - for each composition we keep the most stable one
            comps = {}
            for entry, coords in unstable.items():
                ehull = pd.get_e_above_hull(entry)
                reduced = entry.composition.reduced_formula
                if reduced not in comps:
                    comps[reduced] = [entry, coords, ehull]
                else:
                    if ehull < comps[reduced][-1]:
                        comps[reduced] = [entry, coords, ehull]

            for etype in all_types:
                unstable_coords = []
                unstable_text = []
                unstable_name = []
                dist2hull = []
                nsamples = len(unstable)
                scatter_mode = 'markers' if nsamples > 10 else 'markers+text'
                # Scan through the most stable entry for each composition
                for entry, coords, ehull in comps.values():
                    # Only plot this type, and skip those that are stable
                    if entry_type(entry, 'Unstable'
                                  ) != etype or entry.name in all_stable_names:
                        continue
                    if ehull > self.show_unstable:
                        continue
                    dist2hull.append(ehull)
                    unstable_coords.append(coords)
                    unstable_text.append(entry.name)
                    unstable_name.append(entry_name(entry))
                if not unstable_coords:
                    continue
                a, b, c = list(zip(*unstable_coords))
                aname, bname, cname = map(lambda x: x.name, elems)
                fig.add_scatterternary(
                    a=a,
                    b=b,
                    c=c,
                    marker_symbol='triangle-up',
                    marker_color=dist2hull,
                    #marker_colorbar={'title': 'Dist. to hull'},
                    text=unstable_text,
                    name=f'Unstable ({etype})',
                    mode=scatter_mode,
                    customdata=np.array([unstable_name, dist2hull]).T,
                    hovertemplate=
                    f'{aname}: %{{a:.2f}} {bname}: %{{b:.2f}} {cname}: %{{c:.2f}}<br>name: %{{customdata[0]}}<br>above_hull %{{customdata[1]:.4f}} eV',
                    cliponaxis=False)

        # Plot the end produced
        fig.update_layout({
            'title': f'Ternary plot for {aname}-{bname}-{cname}',
            'ternary': {
                'sum': 1,
                'aaxis': make_axis(elems[0].name, 0),
                'baxis': make_axis(elems[1].name, 45),
                'caxis': make_axis(elems[2].name, -45)
            },
            'autosize': False,
            'height': 600,
            'width': 800,
        })

        return fig


def make_axis(title, tickangle):
    return {
        'title': title,
        'titlefont': {
            'size': 20
        },
        'tickangle': tickangle,
        'showticklabels': False,
        'tickfont': {
            'size': 15
        },
        'tickcolor': 'rgba(0,0,0,0)',
        'ticklen': 5,
        'showline': False,
        'showgrid': True
    }


def entry_type(entry, default):
    """Return the type of and entry"""
    if entry.attribute is None:
        return default
    return entry.attribute.get('entry_type', default)


def entry_name(entry, default='None'):
    """Return the type of and entry"""
    if entry.attribute is None:
        return default
    return entry.attribute.get('struct_name', default)
