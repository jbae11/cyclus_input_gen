import sqlite3 as lite
import sys
from pyne import nucname
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

if len(sys.argv) < 2:
    print('Usage: python analysis.py [cylus_output_file]')


def snf(filename):
    """ prints total snf and isotope mass

    Parameters
    ----------
    filename: int
        cyclus output file to be analyzed.

    Returns
    -------
    Returns total snf and isotope mass.
    """

    sink_id = get_sink_agent_ids()
    resources = cur.execute(exec_string(sink_id, 'transactions.receiverId', '*')).fetchall()
    snf_inventory = cur.execute(exec_string(sink_id, 'transactions.receiverId', 'sum(quantity)')).fetchall()[0][0]
    waste_id = get_waste_id(resources)
    inven = isotope_calc(waste_id, snf_inventory)
    return inven


def get_sink_agent_ids():
    """ Gets all sink agentIds from Agententry table.

        agententry table has the following format:
            SimId / AgentId / Kind / Spec /
            Prototype / ParentID / Lifetime / EnterTime

    Parameters
    ---------
    none

    Returns
    -------
    sink_id: array
        array of all the sink agentId values.
    """

    sink_id = []
    agent = cur.execute("select * from agententry where spec like '%sink%'")

    for ag in agent:
        sink_id.append(ag[1])
    return sink_id


def get_waste_id(resource_array):
    """ Gets waste id from a resource array

    Paramters
    ---------
    resource_array: array
        array fetched from the resource table.

    Returns
    -------
    waste_id: array
        array of qualId for waste
    """

    wasteid = []

    # get all the wasteid
    for res in resource_array:
        wasteid.append(res[7])

    return set(wasteid)


def get_colors():
    """ Gets colors from a matplotlib dictionary

    Parameters
    ----------
    None

    Returns
    -------
    Colors: array
        array of color hex codes
    """

    colors = []
    for hex in matplotlib.colors.cnames.items():
        colors.append(hex[1])
    return colors


def capacity_calc(governments, timestep, entry, exit):
    """ Adds and subtracts capacity over time for plotting

    Paramters
    ---------
    governments: array
        array of governments (countries)
    timestep: array
        array of timestep from 0 to simulation time
    entry: array
        power_cap, agentid, parentid, entertime
        of all entered reactors
    exit: array
        power_cap, agentid, parenitd, exittime
        of all decommissioned reactors
    """

    for gov in governments:
        cap = 0
        count = 0
        for num in timestep:
            for enter in entry:
                if enter[3] == num and enter[2] == gov[1]:
                    cap += enter[0]
                    count += 1
            for dec in exit:
                if dec[3] == num and dec[2] == gov[1]:
                    cap -= dec[0]
                    count -= 1
            exec(gov[0] + '_power.append(cap)')
            exec(gov[0] + '_num.append(count)')


def empty_array_gen(array, suffix_array):
    """ Creates empty arrays with the array + suffix

    Parameters
    ----------
    array: array
        array of items that needs to be created as empty arrays
        only the first colum (index 0) is used.
    suffix_array: array
        array of suffixes

    Returns
    -------
    Creates global variables of empty arrays
    """
    for item in array:
        for suffix in suffix_array:
            exec(item[0] + suffix + ' = []',globals())


def convert_to_numpy(array):
    """ converts array_power array to numpy arrays

    Parameters
    ----------
    array: array
        array to be converted to numpy arrays

    Returns
    -------
    all the array_power are converted to numpy arrays
    """

    for ar in array:
        exec(ar[0] + '_power = np.asarray(' + ar[0] + '_power)')


def stacked_bar_chart(array_sections, timestep, xlabel, ylabel, title):
    """ Creates stacked bar chart of array_sections_power

    Parameters
    ----------
    array_sections: array
        array_power holds plot data (y axis)
    timestep: array
        array of timestep (x axis)
    xlabel: string
        xlabel of plot
    ylabel: string
        ylabel of plot
    title: string
        title of plot

    Returns
    -------
    Stacked bar chart
    """

    # set different colors for each bar
    index = 0
    top_index = True
    prev = ''
    colors = get_colors()

    # plot string for the legend
    plot_string = 'plt.legend(('

    # convert power arrays to numpy arrays for stacking
    for ar in array_sections:
        exec(ar[0] + '_power = np.asarray(' + ar[0] + '_power)')

    # for every country, create bar chart with different color
    for ar in array_sections:
        color = colors[index]
        # very first country does not have a 'bottom' argument
        if top_index == True:
            exec(
                ar[0] + '_plot = plt.bar( 1950+(timestep/12), '
                + ar[0] + '_power, .5, color = color,\
                edgecolor = "none")'
                )
            prev = ar[0] + '_power'
            top_index = False
        # from the second country has 'bottom' argument
        else:
            exec(
                ar[0] + '_plot = plt.bar( 1950+(timestep/12), '
                + ar[0] + '_power, .5, color = color,\
                edgecolor = "none", bottom =' + prev + ')'
                )
            prev += '+ ' + ar[0] + '_power'

        plot_string += ar[0] + '_plot,'
        index += 1

    # generate string for exec of plt.lengend
    plot_string = plot_string[:-1]
    plot_string += '), ('
    for ar in array_sections:
        plot_string += "'" + ar[0] + "', "
    plot_string = plot_string[:-2]
    plot_string += '))'

    # plot
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xlabel(xlabel)
    exec(plot_string)
    plt.grid(True)
    plt.show()


def plot_power(filename):
    """ Gets capacity vs time for every country
        in stacked bar chart.

    Parameters
    ----------
    filename: file
        cyclus output file used

    Returns
    -------
    stacked bar chart of net capapcity vs time

    """

    sim_time = int(cur.execute('SELECT endtime FROM finish').fetchone()[0]) + 1
    timestep = np.linspace(0, sim_time, num=sim_time + 1)
    powercap = []
    reactor_num = []
    countries = []
    # get power cap values

    governments = cur.execute('SELECT prototype, agentid FROM agententry\
                              WHERE spec = ":cycamore:DeployInst"').fetchall()

    entry = cur.execute('SELECT power_cap, agententry.agentid, parentid, entertime\
                        FROM agententry INNER JOIN\
                        agentstate_cycamore_reactorinfo\
                        ON agententry.agentid =\
                        agentstate_cycamore_reactorinfo.agentid').fetchall()

    exit = cur.execute('SELECT power_cap, agentexit.agentid, parentid, exittime\
                        FROM agentexit INNER JOIN\
                        agentstate_cycamore_reactorinfo\
                        ON agentexit.agentid =\
                        agentstate_cycamore_reactorinfo.agentid\
                        INNER JOIN agententry\
                        ON agentexit.agentid = agententry.agentid').fetchall()

    suffixes = ['_power', '_num']
    empty_array_gen(governments, suffixes)

    capacity_calc(governments, timestep, entry, exit)

    convert_to_numpy(governments)

    stacked_bar_chart(governments, timestep, 'Time', 'net_capacity', 'Net Capacity in EU vs Time')
    


def time_vs_waste(filename):
    """ Generates time vs waste
    """


def exec_string(array, search, whatwant):
    """ Generates sqlite query command to select things an
        inner join between resources and transactions.

    Parmaters
    ---------
    array: array
        array of criteria that generates command
    search: str
        where [search]
        criteria for your search
    whatwant: str
        select [whatwant]
        column (set of values) you want out.

    Returns
    -------
    exec_str: str
        sqlite query command.
    """

    exec_str = ('select ' + whatwant + ' from resources inner join transactions\
                on transactions.resourceid = resources.resourceid where '
                + str(search) + ' = ' + str(array[0]))
  
    for ar in array[1:]:
        exec_str += ' or ' + str(ar)

    return exec_str


def isotope_calc(wasteid_array, snf_inventory):
    """ Calculates isotope mass using mass fraction in compositions table.

        Fetches all from compositions table.
        Compositions table has the following format:
            SimId / QualId / NucId / MassFrac
        Then sees if the qualid matches, and if it multiplies
        the mass fraction by the snf_inventory.

    Prameters
    ---------
    wasteid_array: array
        array of qualid of wastes
    snf_inventory: float
        total mass of snf_inventory

    Returns
    -------
    nuclide_inven: array
        inventory of individual nuclides.
    """

    # Get compositions of different commodities
    # SimId / QualId / NucId / MassFrac
    comp = cur.execute('select * from compositions').fetchall()

    nuclide_inven = ['total snf inventory = ' + str(snf_inventory) + 'kg']
    # if the 'qualid's match,
    # the nuclide quantity and calculated and displayed.
    for isotope in comp:
        for num in wasteid_array:
            if num == isotope[1]:
                nuclide_quantity = str(snf_inventory*isotope[3])
                nuclide_name = str(nucname.name(isotope[2]))
                nuclide_inven.append(nuclide_name + ' = ' + nuclide_quantity)

    return nuclide_inven


if __name__ == "__main__":
    file = sys.argv[1]
    con = lite.connect(file)

    with con:
        cur = con.cursor()
        print(snf(file))
        plot_power(file)
