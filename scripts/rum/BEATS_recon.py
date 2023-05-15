#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tomographic reconstruction script for the SESAME BEATS beamline.
For more information, call this script with the help option:
    BEATS_recon.py -h

"""

__author__ = ['Gianluca Iori']
__date_created__ = '2023-05-15'
__date__ = '2023-05-15'
__copyright__ = 'Copyright (c) 2023, SESAME BEATS'
__docformat__ = 'restructuredtext en'
__license__ = "MIT"
__maintainer__ = 'Gianluca Iori'
__email__ = "gianluca.iori@sesame.org.jo"

from argparse import ArgumentParser

import tomopy
import dxchange
import argparse
import textwrap
import logging
from sys import version_info
import numpy as np
# from scipy import ndimage
import numexpr as ne
import os
from time import time
import recon_utils as ru

#################################################################################

def main():
    description = textwrap.dedent('''\
                TomoPy reconstruction script for the BEATS beamline of SESAME.
                ''')
    epilog = textwrap.dedent('''\
                EXAMPLES:

                * Standard (180 degrees, absorption contrast) reconstruction call.
                  Output folder and bitformat are specified:

                    BEATS_recon.py dataset.h5 recon_dir
                    -vs 3.25 3.25 3.25
                    -r 5
                    --voxelfe
                    --template /home/gianthk/PycharmProjects/CT2FE/input_templates/tmp_example01_tens_static.inp

                * Reconstruct using phase retrieval:

                    BEATS_recon.py dataset.h5 recon_dir
                    -vs 3.25 3.25 3.25
                    -r 5
                ''')
    onemoreexample = textwrap.dedent('''
                * 360 degrees reconstruction:

                    BEATS_recon.py dataset.h5 recon_dir
                    -vs 3.25 3.25 3.25
                    -r 5
                    ''')

    parser = argparse.ArgumentParser(description=description, epilog=epilog,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('h5file', type=str, help='<Required> Input HDF5 filename (projection data).')
    parser.add_argument('-s', '--sino', type=int, default=None, help='Specify sinograms to read. (start, end, step)')
    parser.add_argument('--work_dir', type=str, default=None, help='Work folder.')
    parser.add_argument('--recon_dir', type=str, default=None, help='Output reconstruction folder.')
    parser.add_argument('--phase', dest='phase', action='store_true', help='Perform single-step phase retrieval from phase-contrast measurements.')
    parser.add_argument('--alpha', type=float, default=None, help='Phase retrieval regularization parameter.')
    parser.add_argument('--ncore', type=int, default=36, help='Number of cores that will be assigned to jobs.')
    parser.add_argument('--algorithm', type=str, default='gridrec',
						help='Reconstruction algorithm. Options are: gridrec, fbp, fbp_astra, fbp_cuda_astra, sirt, sirt_cuda, sirt_cuda_astra, sart_cuda_astra, cgls_cuda_astra, mlem, art.'
							 'Visit https: // tomopy.readthedocs.io / en / latest / api / tomopy.recon.algorithm.html for more info.')

    parser.add_argument('-vs', '--voxelsize', type=float, default=[1., 1., 1.], nargs='+', help='Voxel size.')
    parser.add_argument('-r', '--resampling', type=float, default=1., help='Resampling factor.')
    parser.add_argument('-s', '--smooth', type=float, nargs='?', const=1., default=0.,
                        help='Smooth image with gaussian filter of given Sigma before thresholding.')
    parser.add_argument('--caps', type=int, default=None,
                        help='Add caps of given thickness to the bottom and top of the model for mesh creation.')
    parser.add_argument('--caps_val', type=int, default=0, help='Caps grey value.')
    parser.add_argument('--shell_mesh', dest='shell_mesh', action='store_true',
                        help='Write VTK mesh of outer shell generated with PyMCubes.')
    parser.add_argument('--vol_mesh', dest='vol_mesh', action='store_true',
                        help='Write VTK volume mesh of tetrahedra with pygalmesh.')
    parser.add_argument('--max_facet_distance', type=float, default=None, help='CGAL mesh parameter.')
    parser.add_argument('--max_cell_circumradius', type=float, default=None, help='CGAL mesh parameter.')
    parser.add_argument('--voxelfe', dest='voxelfe', action='store_true', help='Write voxel FE model (.INP) file.')
    parser.add_argument('--template', type=str, default=None,
                        help='<Required by --voxelfe> Abaqus analysis template file (.INP).')
    parser.add_argument('-m', '--mapping', default=None, nargs='+',
                        help='Template file for material property mapping. If more than one property is given, each property filename must followed by the corresponding GV range.')
    parser.add_argument('--tetrafe', dest='tetrafe', action='store_true',
                        help='Write linear tetrahedra FE model (.INP) file.')
    parser.add_argument('--refnode', default=None, nargs='+',
                        help='Reference node input. Used for kinematic coupling of Boundary Conditions in the analysis template file.'
                             'The REF_NODE coordinates [x,y,z] can be given. Alternatively use one of the following args [X0, X1, Y0, Y1, Z0, Z1] to generate a REF_NODE at a model boundary.')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='Verbose output.')
    parser.set_defaults(shell_mesh=False, vol_mesh=False, phase=False, tetrafe=False, verbose=False)

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

	if args.work_dir is None:
		work_dir = os.path.dirname(args.h5file)
	else:
		work_dir = args.work_dir

	# output reconstruction directory
	if args.recon_dir is None:
		recon_dir = work_dir+"/recon"
	else:
		recon_dir = args.recon_dir

	if not os.path.isdir(recon_dir):
		logging.warning('Reconstruction directory does not extst. Will create it: {}'.format(recon_dir))
		os.mkdir(recon_dir)

	# start reconstruction #################################################################################################
	time_start = time()
	logging.basicConfig(filename=os.path.splitext(args.h5file)[0]+'_recon.log', level=logging.DEBUG)

	# read projections, darks, flats and angles
	if not args.sino:
	    projs, flats, darks, theta = dxchange.read_aps_32id(args.h5file, exchange_rank=0)
	else:
		projs, flats, darks, theta = dxchange.read_aps_32id(args.h5file, exchange_rank=0, sino=args.sino)

	# If the angular information is not available from the raw data you need to set the data collection angles.
	# In this case, theta is set as equally spaced between 0-180 degrees.
	if theta is None:
		theta = tomopy.angles(projs.shape[0])
		logging.info("Theta not found.. generated by TomoPy.")
	logging.info("Theta min: {0}, max: {1}.".format(np.min(theta), np.max(theta)))

	# flat-field correction
	logging.info("Flat-field correct.")
	projs = tomopy.normalize(projs, flats, darks, ncore=args.ncore)

	if args.phase:
		# Perform phase retrieval
		projs = tomopy.retrieve_phase(projs, pixel_size=1e-4 * (4.5 / 1), dist=330, energy=24, alpha=1e-3, pad=True, ncore=ncore, nchunk=None)
	else:
		# Perform - log transform
		logging.info("- log transform.")
		projs = tomopy.minus_log(projs, ncore=ncore)

	# downsample
	# projs = ndimage.zoom(projs, [0.5, 0.5, 1], output=None, order=2)

	# auto detect Center Of Rotation (COR)
	# logging.info("tomopy.find_center..")
	# COR = tomopy.find_center(projs, theta, init=projs.shape[2]/2, tol=1)

	# auto detect Center Of Rotation (COR) witn Vo method
	logging.info("tomopy.find_center_vo..")
	COR = tomopy.find_center_vo(projs)
	logging.info("COR: " + str(COR))

	# COR was found with Vo method + manual inspection
	# logging.info("COR given by user: " + str(COR))

	logging.info("Reconstruct with algorithm: " + algorithm)
	recon_start_time = time()
	if algorithm == 'fbp_astra':
		# CPU ASTRA RECON
		options = {'proj_type': 'linear', 'method': 'FBP'}
		recon = tomopy.recon(projs, theta, center=COR, algorithm=tomopy.astra, options=options, ncore=ncore)
	elif algorithm == 'fbp_cuda_astra':
		# GPU ASTRA RECON (CUDA)
		options = {'proj_type': 'cuda', 'method': 'FBP_CUDA'}
		recon = tomopy.recon(projs, theta, center=COR, algorithm=tomopy.astra, options=options, ncore=10)
	elif algorithm == 'sirt_cuda':
		recon = tomopy.recon(projs, theta, center=COR, algorithm='sirt', sinogram_order=False, accelerated=True, ncore=1)
	elif algorithm == 'sirt_cuda_astra':
		# GPU ASTRA RECON (CUDA)
		extra_options = {'MinConstraint': 0}
		# options = {'proj_type': 'cuda', 'method': 'SIRT_CUDA', 'num_iter': 200, 'extra_options': extra_options}
		options = {'proj_type': 'cuda', 'method': 'SIRT_CUDA', 'num_iter': 100}
		recon = tomopy.recon(projs, theta, center=COR, algorithm=tomopy.astra, options=options, ncore=10)
	elif algorithm == 'sart_cuda_astra':
		options = {'proj_type': 'cuda', 'method': 'SART_CUDA', 'num_iter': 100}
		recon = tomopy.recon(projs, theta, center=COR, algorithm=tomopy.astra, options=options, ncore=10)
	elif algorithm == 'cgls_cuda_astra':
		options = {'proj_type': 'cuda', 'method': 'CGLS_CUDA', 'num_iter': 100}
		recon = tomopy.recon(projs, theta, center=COR, algorithm=tomopy.astra, options=options, ncore=10)
	else:
		# Launch tomopy recon (no ASTRA)
		recon = tomopy.recon(projs, theta, center=COR, algorithm=algorithm, sinogram_order=False, ncore=ncore)

	recon_end_time = time()
	recon_time = recon_end_time - recon_start_time
	logging.info("Recon time: {} s".format(str(recon_time)))

	# write outputs ################################################################################################
	logging.info("Writing outputs..")

	# apply circular mask
	# recon = tomopy.circ_mask(recon, axis=0, ratio=0.95)

	# write output stack of TIFFs as float
	fileout = path_recon+'slice.tiff'
	dxchange.writer.write_tiff_stack(recon, fname=fileout, axis=0, digit=5, start=0, overwrite=True)

	# rescale GV range to uint8 from MIN and MAX of 3D data
	# recon_uint8Range = touint8(recon)

	# apply circ mask
	# recon_uint8Range = tomopy.circ_mask(recon_uint8Range, axis=0, ratio=0.95)

	# write output stack of TIFFs as uint8
	# dxchange.writer.write_tiff_stack(recon_uint8Range, fname=fileout, dtype='uint8', axis=0, digit=5, start=0, overwrite=True)

	# write tiff midplanes (float) with dxchange
	dxchange.writer.write_tiff(recon[int(recon.shape[0] / 2), :, :], fname=work_path+algorithm+'_sliceXY.tiff')
	dxchange.writer.write_tiff(recon[:, int(recon.shape[1] / 2), :], fname=work_path+algorithm+'_sliceXZ.tiff')
	dxchange.writer.write_tiff(recon[:, :, int(recon.shape[2] / 2)], fname=work_path+algorithm+'_sliceYZ.tiff')

	# write midplanes (uint8 TIFFs)
	# writemidplanesDxchange(recon_uint8Range, fileout)

	time_end = time()
	execution_time = time_end - time_start
	logging.info("Recon test completed in {} s".format(str(execution_time)))

	return

if __name__ == '__main__':
    main()

