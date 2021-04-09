import numpy as np
import json


def get_data():


    d = {'units': {'mass': 'kg',
                   'burnup': 'MWd/MTHM',
                   'power': 'MW',
                   'residence_time': 'EFPD',
                   'time': 'days'
                   },
         'pwr': {'source': 'https://ocw.mit.edu/courses/nuclear-engineering/22-06-engineering-of-nuclear-systems-fall-2010/lectures-and-readings/MIT22_06F10_lec06a.pdf',
                 'type': 'PWR',
                 'thermal_power': 3411,
                 'elec_power': 1150,
                 'u_mass': 86270,
                 'num_assem': 193,
                 'u_mass_per_assem': 446.9,
                 'assem_type': '17x17',
                 'rods_per_assem': 264,
                 'cycle_length': 13*30,
                 'burnup': 46270,
                 'num_batch': 3,
                 'enrichment': 4.45
                },
         'bwr': {'source': 'https://ocw.mit.edu/courses/nuclear-engineering/22-06-engineering-of-nuclear-systems-fall-2010/lectures-and-readings/MIT22_06F10_lec06b.pdf',
                 'type': "BWR",
                 'thermal_power': 3323,
                 'elec_power': 1130,
                 'u_mass': 764 * 138.346,
                 'num_assem': 764,
                 'assem_type': 'GE 9x9',
                 'num_batch': 4,
                 'burnup': 45272.3,
                 'enrichment': 4.31, 
                 'u_mass_per_assem': 138.346,
                 'cycle_length': 12*30
                },
         # note: document says cycle length of 18 months,
         # but that will exceed the discharge burnup of 62000 MWd/MTHM,
         # which is the maximum allowed burnup
         # so it's reduced to 17 months
         'ap1000': {"source": ["https://www.nrc.gov/docs/ML0715/ML071580895.pdf",
                               "https://www.nrc.gov/docs/ML1117/ML11171A445.pdf"],
                    "type": "LWR",
                    "thermal_power": 3400,
                    "elec_power": 1117,
                    "n_rod": 41448,
                    "uox_mass": 95974.7024,
                    "u_mass": 84592.98,
                    "rod_per_assem": 264,
                    "num_assem": 157,
                    "uox_mass_per_assem": 611.303,
                    'u_mass_per_assem': 538.808,
                    "assem_type": "17X17 XL",
                    'cycle_length': 17*30, 
                    'fuel_residence_time': 17*30*3,
                    'burnup': 61495.17,
                    'num_batch': 3,
                    "enrichment": [2.35, 3.40, 4.45]
                    },

         'xe100': {"source": "https://www.sciencedirect.com/science/article/abs/pii/S0029549319304467",
                   "u_per_pebble": 0.007,
                   "burnup": 164000,
                   "num_fuel_spheres": 223000,
                   "thermal_power": 200,
                   "elec_power": 80,
                   "fuel_residence_time": 1273,
                   "core_u_mass": 1561,
                   "discharge_mass_per_month": 36.585,
                   "discharge_per_year": 439.024,
                   'enrichment':15.5
                   }
        }

    return d