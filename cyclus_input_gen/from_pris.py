import copy
import sys
import jinja2
import numpy as np
import os
from datetime import datetime
from cyclus_input_gen.templates import template_collections


class from_pris:
    def __init__(self, csv_file, init_date, duration,
                 country_list, output_file='complete_input.xml',
                 reprocessing=True, special=''):
        """ Generates cyclus input file from csv files and jinja templates.

        Parameters
        ---------
        csv_file : str
            csv file containing reactor data (country, name, net_elec_capacity)
        init_date: int
            yyyymmdd format of initial date of simulation
        input_template: str
            template file for entire complete cyclus input file
        country_list: list of str
            list of countries to take into account
        output_file: str
            directory and name of complete cyclus input file
        reprocessing: bool
            True if reprocessing is done, False if not

        Returns
        -------
        File with reactor section of cyclus input file
        File with region section of cyclus input file
        File with complete cyclus input file
        """
        self.csv_file = csv_file
        self.init_date = init_date
        self.duration = duration
        self.country_list = country_list
        self.output_file = output_file
        self.reprocessing = reprocessing
        self.special = special
        self.done_generic = False

        self.reactor_data = self.read_csv()
        for data in self.reactor_data:
            #print(data['reactor_name'])
            #print(int(data['first_crit']))
            #print(type(data['first_crit']))
            data['commercial'] = int(data['commercial'].decode('utf-8'))
            #print(data['first_crit'])
            entry_time = self.get_entrytime(self.init_date, data['commercial'])
            lifetime = self.get_lifetime(data['commercial'], data['shutdown_date'])
            if entry_time <= 0:
                lifetime = max(lifetime + entry_time, 0)
                entry_time = 1
            data['entry_time'] = entry_time
            data['lifetime'] = lifetime

        self.reactor_render()
        self.region_render()
        self.input_render()
        if 'f33' in special:
            print('Makes sure you fill in the following:')
            print('\t$f33_path')
            print('\t$scalerte_path')
            print('\t$bu_randomness_frac')

    

    def read_csv(self):
        """This function reads the csv file and returns the list.

        Parameters
        ---------
        csv_file: str
            csv file that lists country, reactor name, net_elec_capacity etc.

        Returns
        -------
        reactor_array:  list
            array with the data from csv file
        """
        reactor_array = np.genfromtxt(self.csv_file,
                                      skip_header=2,
                                      delimiter=',',
                                      dtype=('S128', 'S128',
                                             'S128', 'int',
                                             'S128', 'S128', 'S128',
                                             'int', 'S128',                                         
                                             'S128', 'S128',
                                             'S128', 'float',
                                             'float', 'float',
                                             'int', 'int'),
                                      names=('country', 'reactor_name',
                                             'type', 'net_elec_capacity',
                                             'status', 'operator', 'const_date',
                                             'cons_year', 'first_crit',
                                             'first_grid', 'commercial',
                                             'shutdown_date', 'ucf',
                                             'lat', 'long',
                                             'entry_time', 'lifetime'))
        new_reactor = copy.deepcopy(reactor_array)
        reactor_array = new_reactor
        indx_list = []
        for indx, reactor in enumerate(reactor_array):
            if reactor['country'].decode('utf-8') not in self.country_list:
                indx_list.append(indx)
            nono_str_list = ['cancel', 'defer', 'review', 'suspend', 'under']
            for i in nono_str_list:
                if i in reactor['status'].decode('utf-8').lower():
                    indx_list.append(indx)
        reactor_array = np.delete(reactor_array, indx_list, axis=0)

        # convert dates to standard date format
        for indx, reactor in enumerate(reactor_array):
            reactor_array[indx]['const_date'] = int(self.std_date_format(
                reactor['const_date']))
            reactor_array[indx]['first_crit'] = int(self.std_date_format(reactor['first_crit']))
            reactor_array[indx]['first_grid'] = int(self.std_date_format(
                reactor['first_grid']))
            reactor_array[indx]['commercial'] = int(self.std_date_format(
                reactor['commercial']))
            reactor_array[indx]['shutdown_date'] = int(self.std_date_format(
                reactor['shutdown_date']))

        # filter reactors with less than 100 MWe (research reactors)
        return [row for row in reactor_array if row['net_elec_capacity'] > 100]


    def std_date_format(self, date_string):
        """ This function converts date format
        MM/DD/YYYY to YYYYMMDD

        Parameters:
        -----------
        date_string: str
            string with date
        
        Returns:
        --------
        date: int
            integer date with format YYYYMMDD
        """
        date_string = date_string.decode('utf-8')

        if date_string.count('/') == 2:
            obj = datetime.strptime(date_string, '%m/%d/%Y')
            return int(obj.strftime('%Y%m%d'))
        if len(date_string) == 4:
            # default first of the year if only year is given
            return int(date_string + '0101')
        if date_string == '':
            return int(-1)
        return int(date_string)



    def get_ymd(self, yyyymmdd):
        """This function extracts year and month value from yyyymmdd format

            The month value is rounded up if the day is above 16

        Parameters
        ---------
        yyyymmdd: int
            date in yyyymmdd format

        Returns
        -------
        year: int
            year
        month: int
            month
        """
        yyyymmdd = int(yyyymmdd)
        year = yyyymmdd // 10000
        month = (yyyymmdd // 100) % 100
        day = yyyymmdd % 100
        if day > 16:
            month += 1
        return year, month


    def get_lifetime(self, start_date, end_date):
        """This function gets the lifetime for a prototype given the
           start and end date.

        Parameters
        ---------
        start_date: int
            start date of reactor - first criticality.
        end_date: int
            end date of reactor - null if not listed or unknown

        Returns
        -------
        lifetime: int
            lifetime of the prototype in months

        """

        if int(end_date) != -1:
            end_year, end_month = self.get_ymd(end_date)
            start_year, start_month = self.get_ymd(start_date)
            dmonth = self.calc_dmonth(start_year, start_month,
                                      end_year, end_month)
            return dmonth

        else:
            return 720


    def get_entrytime(self, init_date, start_date):
        """This function converts the date format and saves it in variables.

            All dates are in format - yyyymmdd

        Parameters
        ---------
        init_date: int
            start date of simulation
        start_date: int
            start date of reactor - first criticality.

        Returns
        -------
        entry_time: int
            timestep of the prototype to enter

        """
        start_date = int(start_date)
        init_year, init_month = self.get_ymd(init_date)
        start_year, start_month = self.get_ymd(start_date)

        dmonth = self.calc_dmonth(init_year, init_month,
                                  start_year, start_month)
        print(init_date, start_date, dmonth)
        return dmonth



    def calc_dmonth(self, yi, mi, yf, mf):
        dy = yf - yi
        dm = mf - mi
        return 12*dy + dm


    def read_template(self, template):
        return jinja2.Template(template)

    def refine_name(self, name):
        name = name.decode('utf-8')
        start = name.find('(')
        end = name.find(')')
        if start != -1 and end != -1:
            name = name[:start]
        name = name.replace(r'&', 'and')
        return name


    def reactor_render(self):
        self.reactor_str = ''
        template_dict = {}
        for reactor in ['pwr', 'mox', 'candu', 'smr']:
            template_dict[reactor] = getattr(template_collections, reactor+'_template')

        if 'cyborg' in self.special:
            for reactor in ['pwr', 'mox', 'candu']:
                template_dict[reactor] = getattr(template_collections, reactor+'_template_cyborg')

        if 'f33' in self.special:
            template_dict['pwr'] = getattr(template_collections, 'pwr_template_f33')

        template_dict = {k:self.read_template(v) for k, v in template_dict.items()}


        # from NRC application
        ap1000_spec = {'template': template_dict['pwr'],
                       'kg_per_assembly': 612.5 * 157 / 3300 ,
                       'assemblies_per_core': 3,
                       'assemblies_per_batch': 1}
        bwr_spec = {'template': template_dict['pwr'],
                    'kg_per_assembly': 180 * 764 / 4392.0,
                    'assemblies_per_core': 4,
                    'assemblies_per_batch': 1}
        phwr_spec = {'template': template_dict['candu'],
                     'kg_per_assembly': 8000 / 473,
                     'assemblies_per_core': 473 / 500.0,
                     'assemblies_per_batch': 60}
        candu_spec = {'template': template_dict['candu'],
                      'kg_per_assembly': 8000 / 473,
                      'assemblies_per_core': 473 / 500.0,
                      'assemblies_per_batch': 60}
        pwr_spec = {'template': template_dict['pwr'],
                    'kg_per_assembly': 446.0 * 193 / 3000.0,
                    'assemblies_per_core': 3,
                    'assemblies_per_batch': 1}
        epr_spec = {'template': template_dict['pwr'],
                    'kg_per_assembly': 467.0 * 216 / 4800,
                    'assemblies_per_core': 3,
                    'assemblies_per_batch': 1}
        smr_spec = {'template': template_dict['smr'],
                    'kg_per_assembly': 2997.12 / 50,
                    'assemblies_per_core': 3,
                    'assemblies_per_batch': 1}
        pow_dict = {'AP1000': 1110,
                    'BWR': 1260,
                    'PWR': 1000,
                    'EPR': 1600,
                    'SMR': 50,
                    '12_SMR': 600
                    }
        reactor_specs = {'AP1000': ap1000_spec,
                     #'PHWR': phwr_spec,
                     'BWR': bwr_spec,
                     #'CANDU': candu_spec,
                     'PWR': pwr_spec,
                     'EPR': epr_spec,
                     'SMR': smr_spec}

        for data in self.reactor_data:
            # refine name string
            name = self.refine_name(data['reactor_name'])
            reactor_type = data['type'].decode('utf-8')
            if reactor_type in reactor_specs.keys():
                # if the reactor type matches with the pre-defined dictionary,
                # use the specifications in the dictionary.
                spec_dict = reactor_specs[reactor_type]
                reactor_body = spec_dict['template'].render(
                    country=data['country'].decode('utf-8'),
                    type=reactor_type,
                    reactor_name=name,
                    assem_size=round(spec_dict['kg_per_assembly'] * data['net_elec_capacity'], 3),
                    n_assem_core=spec_dict['assemblies_per_core'],
                    n_assem_batch=spec_dict['assemblies_per_batch'],
                    capacity=data['net_elec_capacity'])
            else:
                # assume 1000MWe pwr linear core size model if no match
                reactor_body = template_dict['pwr'].render(
                    country=data['country'].decode('utf-8'),
                    reactor_name=name,
                    type=reactor_type,
                    assem_size=523.4*193/3000 * data['net_elec_capacity'],
                    n_assem_core=3,
                    n_assem_batch=1,
                    capacity=data['net_elec_capacity'])

            self.reactor_str += reactor_body + '\n'

        if not self.done_generic:
            for key, val in pow_dict.items():
                k = key.replace('12_', '')
                spec_dict = reactor_specs[k]
                reactor_body = spec_dict['template'].render(
                        country=data['country'].decode('utf-8'),
                        type=key,
                        reactor_name=key,
                        assem_size=round(spec_dict['kg_per_assembly'] * val, 3),
                        n_assem_core=spec_dict['assemblies_per_core'],
                        n_assem_batch=spec_dict['assemblies_per_batch'],
                        capacity=val)
                self.reactor_str += reactor_body + '\n'
            self.done_generic = True


    def region_render(self):
        """Takes the list and template and writes a region file

        Parameters
        ---------
        reactor_data: list
            list of data on reactors
        output_file: str
            name of output file

        Returns
        -------
        The region section of cyclus input file

        """
        template = self.read_template(template_collections.deployinst_template)
        full_template = self.read_template(template_collections.region_output_template)
        sd = {}
        country_list = []
        empty_country = []
        valhead = '<val>'
        valtail = '</val>'

        country_set = set([data['country'].decode('utf-8') for data in self.reactor_data])

        for country in country_set:
            prototype = ''
            entry_time = ''
            n_build = ''
            lifetime = ''
            sd[country] = ''

            # for every reactor data corresponding to a country, create a
            # string with its region block
            for data in [q for q in self.reactor_data if q['country'].decode('utf-8') == country]:
                if data['lifetime'] <= 0:
                    continue
                prototype += valhead + self.refine_name(data['reactor_name']) + valtail + '\n'
                entry_time += valhead + str(data['entry_time']) + valtail + '\n'
                n_build += valhead + '1' + valtail + '\n'
                lifetime += valhead + str(data['lifetime']) + valtail + '\n'

            render_temp = template.render(prototype=prototype,
                                          start_time=entry_time,
                                          number=n_build,
                                          lifetime=lifetime)
            if prototype != '':
                sd[country] += render_temp
            else:
                empty_country.append(country)

        country_set = [q for q in country_set if q not in empty_country]
        full_str = ''
        for country in country_set:
            country_body = full_template.render(country=country,
                                                country_gov=country+'_government',
                                                deployinst=sd[country])
            full_str += country_body + '\n'

        self.region_str = full_str


    def input_render(self):
        template = self.read_template(template_collections.input_template)
        startyear, startmonth = self.get_ymd(self.init_date)

        if self.reprocessing:
            reprocessing_chunk = """<entry>
    <number>1</number>
    <prototype>reprocessing</prototype>
</entry>\n"""
        else:
            reprocessing_chunk = ''

        rendered_template = template.render(duration=self.duration,
                                            startmonth=startmonth,
                                            startyear=startyear,
                                            reprocessing=reprocessing_chunk,
                                            reactor_input=self.reactor_str,
                                            region_input=self.region_str)
        if 'f33' in self.special:
            f33_str = '<spec><lib>f33_reactor.f33_reactor</lib><name>f33_reactor</name></spec></archetypes>'
            rendered_template = rendered_template.replace('</archetypes>', f33_str)

        with open(self.output_file, 'w') as output:
            output.write(rendered_template)





