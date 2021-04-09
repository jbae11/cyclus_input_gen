import copy
import sys
import jinja2
import numpy as np
import os
import pandas as pd
from datetime import datetime
from cyclus_input_gen.templates import template_collections
from cyclus_input_gen.reactor_specs import get_data

class from_pris:
    def __init__(self, csv_file, init_date, duration,
                 country_list, assumed_lifetime=720,
                 output_file='complete_input.xml',
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
        self.init_date = self.process_init_date(init_date)
        self.duration = duration
        self.country_list = country_list
        self.output_file = output_file
        self.assumed_lifetime = assumed_lifetime
        self.reprocessing = reprocessing
        self.special = special
        self.done_generic = False

        self.reactor_data = self.read_csv()

        self.reactor_data['entry_time'] = self.get_entrytime(self.reactor_data['Commercial Date'])
        self.reactor_data['lifetime'] = self.get_lifetime(list(self.reactor_data['entry_time']),
                                                          list(self.reactor_data['Shutdown Date']))
        # edit entry time to have at least 1
        self.reactor_data['entry_time'] = [max(1, q) for q in self.reactor_data['entry_time']]

        self.reactor_render()
        self.region_render()
        self.input_render()
        if 'f33' in special:
            print('Makes sure you fill in the following:')
            print('\t$f33_path')
            print('\t$scalerte_path')
            print('\t$bu_randomness_frac')


    def process_init_date(self, init_date):
        year, month, day = init_date//10000, init_date%10000//100, init_date%100
        return pd.to_datetime(f'{year}/{month}/{day}')


    def get_entrytime(self, reactor_start_date):
        dt = [q - self.init_date for q in list(reactor_start_date)]
        # in months
        dt = [int(q.total_seconds() / (3600 * 24 * 30)) for q in dt]
        return dt


    def get_delta_month(self, t0, t1):
        dt = t1 - t0
        return dt.total_seconds() / (3600 * 24 * 30)


    def get_lifetime(self, entrytime, shutdown_date):
        lifetime_list = []

        for indx in range(len(entrytime)):
            if str(shutdown_date[indx]) == 'NaT':
                if entrytime[indx] < 0:
                    lifetime_list.append(self.assumed_lifetime + entrytime[indx])
                else:
                    lifetime_list.append(self.assumed_lifetime)
            else:
                lifetime_list.append(self.get_delta_month(self.init_date, shutdown_date[indx]))
        return lifetime_list


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
        df = pd.read_csv(self.csv_file, skiprows=1)
        # check if countries are valid
        for country in self.country_list:
            if country not in df.Country.unique():
                print(df.Country.unique())
                raise ValueError('Country not in list')
        filtered_df = df[df['Country'].isin(self.country_list)]

        # filter reactors that are not built
        bad_status_list = ['Review Suspended', 'Suspended Constr.', 'Deferred', 'Cancelled Constr.',
                           'Under Review', 'Under Construction']
        filtered_df = filtered_df[~filtered_df['Status'].isin(bad_status_list)]

        # filter reactors that are already gone
        filtered_df = filtered_df[filtered_df['Status'] != 'Permanent Shutdown']

        # filter reactors with less than 100MWe (research reactors)
        filtered_df = filtered_df[filtered_df['Net Capacity (MWe)'] > 100]

        # convert dates to datetime format
        for column in ['First Criticality Date', 'First Grid Date',
                       'Commercial Date', 'Shutdown Date']:
            filtered_df[column] = pd.to_datetime(filtered_df[column])

        # refine name
        filtered_df['Reactor Unit'] = [self.refine_name(q) for q in filtered_df['Reactor Unit']]

        return filtered_df


    def read_template(self, template):
        return jinja2.Template(template)

    def refine_name(self, name):
        name = name
        start = name.find('(')
        end = name.find(')')
        if start != -1 and end != -1:
            name = name[:start]
        name = name.replace(r'&', 'and')
        return name

    def get_position_str(self, row):
        longitude = row['Longitude']
        latitude = row['Latitude']
        if np.isnan(longitude): return ''
        return '<latitude>%s</latitude><longitude>%s</longitude>' %(latitude, longitude)


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

        reactor_spec_data = get_data()
        ap1000 = reactor_spec_data['ap1000']
        bwr = reactor_spec_data['bwr']
        pwr = reactor_spec_data['pwr']
        # from NRC application
        # assemblies per core is normalized by capcity
        ap1000_spec = {'template': template_dict['pwr'],
                       'kg_per_assembly': ap1000['u_mass']/(ap1000['elec_power']*ap1000['num_batch']) ,
                       'assemblies_per_core': ap1000['num_batch'],
                       'cycle_time': ap1000['cycle_length']/30,
                       'refuel_time': 1,
                       'assemblies_per_batch': 1}
        bwr_spec = {'template': template_dict['pwr'],
                    'kg_per_assembly': bwr['u_mass'] / (bwr['elec_power']*bwr['num_batch']),
                    'assemblies_per_core': bwr['num_batch'],
                    'cycle_time': bwr['cycle_length']/30,
                    'refuel_time': 1,
                    'assemblies_per_batch': 1}
        pwr_spec = {'template': template_dict['pwr'],
                    'kg_per_assembly': pwr['u_mass'] / (pwr['elec_power'] * pwr['num_batch']),
                    'assemblies_per_core': pwr['num_batch'],
                    'cycle_time': pwr['cycle_length']/30,
                    'refuel_time': 1,
                    'assemblies_per_batch': 1}

        phwr_spec = {'template': template_dict['candu'],
                     'kg_per_assembly': 8000 / 473,
                     'assemblies_per_core': 473 / 500.0,
                     'assemblies_per_batch': 60,
                     'cycle_time': 1,
                    'refuel_time': 0,}
        candu_spec = {'template': template_dict['candu'],
                      'kg_per_assembly': 8000 / 473,
                      'assemblies_per_core': 473 / 500.0,
                      'cycle_time': 1,
                      'refuel_time': 0,
                      'assemblies_per_batch': 60}
        epr_spec = {'template': template_dict['pwr'],
                    'kg_per_assembly': 467.0 * 216 / 4800,
                    'cycle_time': 14,
                    'refuel_time': 1,
                    'assemblies_per_core': 3,
                    'assemblies_per_batch': 1}
        smr_spec = {'template': template_dict['smr'],
                    'kg_per_assembly': 2997.12 / 50,
                    'cycle_time': 12,
                    'refuel_time': 1,
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

        print(f'Rendering {len(self.reactor_data)} reactors..')
        for indx, row in self.reactor_data.iterrows():

            name = row['Reactor Unit']
            reactor_type = row['Type']
            country = row['Country']
            capacity = row['Net Capacity (MWe)']
            position_str = self.get_position_str(row)
            if not position_str:
                print(f'{name} does not have any position data - leaving it blank.')
            if reactor_type in reactor_specs.keys():
                # if the reactor type matches with the pre-defined dictionary,
                # use the specifications in the dictionary.
                spec_dict = reactor_specs[reactor_type]
                reactor_body = spec_dict['template'].render(
                    country=country,
                    type=reactor_type,
                    reactor_name=name,
                    refuel_time=int(spec_dict['refuel_time']),
                    cycle_time=int(spec_dict['cycle_time']),
                    assem_size=round(spec_dict['kg_per_assembly'] * capacity, 3),
                    n_assem_core=spec_dict['assemblies_per_core'],
                    n_assem_batch=spec_dict['assemblies_per_batch'],
                    capacity=capacity,
                    position_=position_str)
            else:
                # assume 1000MWe pwr linear core size model if no match
                reactor_body = template_dict['pwr'].render(
                    country=country,
                    reactor_name=name,
                    type=reactor_type,
                    assem_size=pwr['u_mass']/pwr['thermal_power'] * capacity,
                    refuel_time=1,
                    cycle_time=14,
                    n_assem_core=3,
                    n_assem_batch=1,
                    capacity=capacity,
                    position_=position_str)

            self.reactor_str += reactor_body + '\n'

        if not self.done_generic:
            for key, val in pow_dict.items():
                k = key.replace('12_', '')
                spec_dict = reactor_specs[k]
                reactor_body = spec_dict['template'].render(
                        country='Generic',
                        type=key,
                        reactor_name=key,
                        refuel_time=int(spec_dict['refuel_time']),
                        cycle_time=int(spec_dict['cycle_time']),
                        assem_size=round(spec_dict['kg_per_assembly'] * val, 3),
                        n_assem_core=spec_dict['assemblies_per_core'],
                        n_assem_batch=spec_dict['assemblies_per_batch'],
                        capacity=val,
                        position_=position_str)
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

        country_set = self.reactor_data.Country.unique()

        for country in country_set:
            prototype = ''
            entry_time = ''
            n_build = ''
            lifetime = ''
            sd[country] = ''

            # for every reactor data corresponding to a country, create a
            # string with its region block
            filtered_df = self.reactor_data[self.reactor_data['Country'] == country]
            for indx, row in filtered_df.iterrows():
                if row['lifetime'] <= 0:
                    continue
                prototype += valhead + row['Reactor Unit'] + valtail + '\n'
                entry_time += valhead + str(row['entry_time']) + valtail + '\n'
                n_build += valhead + '1' + valtail + '\n'
                lifetime += valhead + str(row['lifetime']) + valtail + '\n'

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
        startyear, startmonth = self.init_date.year, self.init_date.month

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





