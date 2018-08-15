import multiprocessing
import time
import os
from seqfish_config24bit_ca_cell_v2 import * #needs this for the deconvolution kernels maybe use gauss or separate in another file??
from metadata import Metadata
from scipy import ndimage
from skimage import io
from codestack_creation import * # not sure why needed?

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("md_path", type=str, help="Path to root of imaging folder to initialize metadata.")
parser.add_argument("-p", "--nthreads", type=int, dest="ncpu", default=52, action='store', nargs=1, help="Number of cores to utilize (default 52).")
args = parser.parse_args()
print(args)

def dogonvole(image, psf, kernel=(2., 2., 0.), blur=(1.3, 1.3, 0.), niter=12):
    """
    Perform deconvolution and difference of gaussian processing.
    Parameters
    ----------
    image : ndarray
    psf : ndarray
    kernel : tuple
    blur : tuple
    niter : int
    
    Returns
    -------
    image : ndarray
        Processed image same shape as image input.
    """
    if not psf.sum() == 1.:
        raise ValueError("psf must be normalized so it sums to 1")
    image = image.astype('float32')
    img_bg = ndimage.gaussian_filter(image, kernel[:len(image.shape)])
    image = numpy.subtract(image, img_bg)
    numpy.place(image, image<0, 1./2**16)
    image = image.astype('uint16')
    if len(image.shape)==3:
        for i in range(image.shape[2]):
            image[:,:,i] = restoration.richardson_lucy(image[:,:,i], psf, niter, clip=False)
    elif len(image.shape)==2:
        image = restoration.richardson_lucy(image, psf, niter, clip=False)
    else:
        raise ValueError('image is not a supported dimensionality.')
    image = ndimage.gaussian_filter(image, blur[:len(image.shape)])
    return image


def process_image_postimaging(fname, min_thresh=5./2**16, niter=15, uint8=False):
    """    
    Parameters
    ----------
    fname : str
        Filename of a tiff image to process
    min_thresh : float
        Minimum intensity will become 0 in output
    niter : int
        Number of iterations of deconvolution to perform.
    
    Returns
    -------
    Nothing but new file is written
    
    Notes - currently save locations are hardcoded inside here.
    Also psf's are imported during config file import and globals.
    """
    global orange_psf, green_psf, farred_psf
    cstk = io.imread(fname).astype('float32')#/2.**16
    
    if 'DeepBlue' in fname:
#         xs, ys = yshift_db+tvect[0], xshift_db+tvect[1]
#        return cstk.astype('uint16')
        pass
    elif 'Orange' in fname:
        #xs, ys = numpy.linspace(0, 2047, 2048)+tvect[0], numpy.linspace(0, 2047, 2048)+tvect[1]
        cstk = dogonvole(cstk, orange_psf, niter=niter)
    elif 'Green' in fname:
        #xs, ys = yshift_g+tvect[0], xshift_g+tvect[1]
        cstk = dogonvole(cstk, green_psf, niter=niter)
    elif 'FarRed' in fname:
        #xs, ys = yshift_fr+tvect[0], xshift_fr+tvect[1]
        cstk = dogonvole(cstk, farred_psf, niter=niter)
    else:
        print('unmet name', fname)
    if uint8:
        cstk = cstk/2**6
        io.imsave(fname, cstk.astype('uint8'))
    else:
        io.imsave(fname, cstk.astype('uint16'))
    return fname

def worker(fname, q):
    '''stupidly simulates long running process'''
    try:
    	freturn = process_image_postimaging(fname)
    except Exception as e:
        print(e)
#    print(fname)
    q.put(fname)

def main(md_path, fn, ncpu, chunksize):
    with multiprocessing.Pool(ncpu) as p:
        md = Metadata(md_path)
        all_images = md.image_table.filename.values
        if os.path.exists(fn):
            doneso = {i.strip():1 for i in open(fn, 'r').readlines()}
            all_images = [i for i in all_images if i not in doneso]
        else:
            doneso = {}
            f = open(fn, 'w')
            f.close()
        tstart = time.time()
        print('Starting...', 'already done ', str(len(doneso)), ', but ', str(len(all_images)), 'left')
        with open(fn, 'a') as f:
            for result in p.imap(process_image_postimaging, all_images, chunksize=chunksize):
                f.write(str(result)+'\n')
        tend = time.time()
    print('Finished processing ', str(len(all_images)), 'images in ', str(tend-tstart), 'seconds.')
       
    
if __name__ == "__main__":
    #md_path = '/data/hybe_endo_100k_2018Aug06'
    #fn = '/home/rfor10/deconv_endos.log'
#    md_path = sys.argv[1]
    fn = os.path.join(args.md_path, 'processing.log')
    chunksize=1
    os.environ['MKL_NUM_THREADS'] = '1'
    os.environ['GOTO_NUM_THREADS'] = '1'
    os.environ['OMP_NUM_THREADS'] = '1'
    main(args.md_path, fn, args.ncpu, chunksize)