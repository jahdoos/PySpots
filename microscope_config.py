import pickle
import numpy
import os
from skimage.io import imread

################################ Microscope Related Config ##########################
image_size = (2048, 2048)

base_pth = '/home/rfor10/repos/PySpots'
ave_bead = pickle.load(open(os.path.join(base_pth, 'ave_bead.333um.pkl'), 'rb'))

# This .pkl file needs to be in the spot_calling repository/directory
chromatic_dict = pickle.load(open(os.path.join(base_pth, './jan2018_chromatic.pkl'), 'rb')) # Warning File import

xshift_fr = numpy.add(chromatic_dict['orange_minus_farred'][0], range(image_size[0]))
yshift_fr = numpy.add(chromatic_dict['orange_minus_farred'][1], range(image_size[1]))

xshift_g = numpy.add(chromatic_dict['orange_minus_green'][0], range(image_size[0]))
yshift_g = numpy.add(chromatic_dict['orange_minus_green'][1], range(image_size[1]))

xshift_db = numpy.add(chromatic_dict['orange_minus_deepblue'][0], range(image_size[0]))
yshift_db = numpy.add(chromatic_dict['orange_minus_deepblue'][1], range(image_size[1]))

farred_psf = imread(os.path.join(base_pth, 'farred_psf_fit_250nmZ_63x.tif'))
farred_psf = farred_psf[25, 8:17, 8:17]
farred_psf = farred_psf/farred_psf.sum()
green_psf = imread(os.path.join(base_pth, 'green_psf_fit_250nmZ_63x.tif'))
green_psf = green_psf[28, 5:14, 5:14]
green_psf = green_psf/green_psf.sum()
orange_psf = imread(os.path.join(base_pth, '63x_psf_orange_250nmZ.tif'))
orange_psf = orange_psf[25,  5:14, 5:14]
orange_psf = orange_psf/orange_psf.sum()