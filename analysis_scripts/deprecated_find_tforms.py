import pickle
from metadata import Metadata
import imreg_dft as ird
from scipy.spatial import KDTree
from scipy import optimize
import numpy as np
import os
from collections import defaultdict
from functools import partial
import multiprocessing
from scipy.ndimage import gaussian_filter
import traceback
from hybescope_config.microscope_config import *

# Protecting this block in if allows functions to be imported independently
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("md_path", type=str, help="Path to root of imaging folder to initialize metadata.")
    parser.add_argument("bead_path", type=str, help="Path pickle dictionary of candidate beads per position name.")
    parser.add_argument("out_path", type=str, help="Path to save output.")
    parser.add_argument("-p", "--nthreads", type=int, dest="ncpu", default=4, action='store', nargs=1, help="Number of cores to utilize (default 4).")

    # parser.add_argument("--hotpixels", type=str, dest="hot_pixel_pth", default='/home/rfor10/repos/PySpots/hot_pixels_aug2018.pkl', action='store', nargs=1, help="Path to file to use for hot pixels.")
    args = parser.parse_args()
    print(args)

def hybe_composite(md_pth, posname, channels = ['DeepBlue'],
                   zindexes=None, nhybes = 9):
    """
    Create maximum projection composites from each hybe.
    """
    hybe_names = ['hybe'+str(i) for i in range(1, nhybes+1)]
    md = Metadata(md_pth)
    if zindexes is None:
        zindexes = list(md.image_table.Zindex.unique())
    hybe_composites = {}
    for h in hybe_names:
        hybe_stk = md.stkread(Channel=channels, Position=posname, Zindex=zindexes, hybe=h)
        hybe_stk = hybe_stk.max(axis=2)
        for y, x in hot_pixels:
            hybe_stk[y, x] = 0
        hybe_composites[h] = hybe_stk
    return hybe_composites

def xcorr_hybes(hybe_dict, reg_ref = 'hybe1', bead_thresh=10000):
    """
    Find the translation xcorr between hybes.
    """
    tvecs = {}
    ref_img = hybe_dict[reg_ref]
#     img_bg = gaussian_filter(ref_img, (10, 10))
#     ref_hpass = ref_img-img_bg
#     np.place(ref_hpass, ref_hpass<bead_thresh, 0.01)
    for h, img in hybe_dict.items():
        if h == reg_ref:
            tvecs[h] = (0,0)
        else:
#             img_bg = gaussian_filter(img, (10, 10))
#             img_hpass = img-img_bg
#             np.place(img_hpass, img_hpass<bead_thresh, 0.01)
            xcorr_result = ird.translation(ref_img, img)
            tvecs[h] = xcorr_result['tvec']
    return tvecs


def wrappadappa_bead_xcorr(posname, md_pth):
    bead_projections = hybe_composite(md_pth, posname, channels=['DeepBlue'], zindexes=None, nhybes=9)
    tvecs = xcorr_hybes(bead_projections)
    return posname, tvecs

# Functions to use new bead fitting routine (use example)
# func_inputs = [(bead_pos_dicts[pos], seed_tforms[pos]) for pos in posnames]
# bead_pos_dicts is dictionary of dictionarys
    #pos:hybe_dict where hybe_dict is hybe_name:bead_array
# seed_tforms is dictionary created by above functions



def find_pair_error(tvect, beads1, beads2, return_more=False):
    beads2_reg = beads2+tvect
    tree = KDTree(beads1)
    b2_pair = [tree.query(p) for p in beads2_reg]
    dists, idx = zip(*b2_pair)
    b2_pair = [beads1[i] for i in idx]
    naccepted, idx = reject_outliers(dists)
    for i in range(10):
        naccepted, idx = reject_outliers(naccepted)
    naccepted2, idx = reject_outliers(naccepted)
    residual = np.abs(np.mean(naccepted2))
    if return_more:
        return residual, len(naccepted2), len(dists)
    else:
        return residual

def reject_outliers(data, m=2):
    """
    Reject outliers for robust distance estimation.
    (Bead candidates could be incorrect or their cognate pair could be
    missing in the cognate hybe)
    """
    data = np.array(data)
    good_idx = abs(data - np.mean(data)) < m * np.std(data)
    return data[good_idx], good_idx

def optimize_tforms(bead_dict, seed_tforms, reg_ref='hybe1', verbose=False):
    """
    New registration method. Find seed tforms by xcorrelation then optimize with
    the bead candidate coordinates.
    """
    #pos = posnames[11]
    bead_dict = bead_dict.copy()
    seed_tforms = seed_tforms.copy()
    try:
        if 'nucstain' in bead_dict:
            nucs = bead_dict.pop('nucstain')
            popped = True
        else:
            popped=False
        reg_ref = 'hybe1'
        opt_tforms = {}
        tform_quality_metrics = defaultdict(dict)
        bead_ref = bead_dict.pop(reg_ref)
        for h, bead_dest in bead_dict.items():
            initial = seed_tforms[h]
            initial = (initial[0], initial[1], 0)
            tvect = optimize.fmin(find_pair_error, initial,
                                     args=(bead_ref, bead_dest), disp=verbose)
            opt_tforms[h] = tvect
            residual, naccepted2, dists = find_pair_error(tvect, bead_ref, bead_dest, return_more=True)
            tform_quality_metrics[h]['nbeads'] = naccepted2
            tform_quality_metrics[h]['bead_outlier_ratio'] = naccepted2/dists
            tform_quality_metrics[h]['residual'] = residual
            tform_quality_metrics[h]['all_bead_dists'] = dists
            tform_quality_metrics[h]['accepted_bead_dists'] = naccepted2
        opt_tforms[reg_ref] = np.array((0,0,0))
        bead_dict[reg_ref] = bead_ref
        if popped:
            bead_dict['nucstain'] = nucs
        return opt_tforms, tform_quality_metrics
    except Exception as e:
        print(e)
        print(traceback.print_exc())
        return 'Error'

if __name__ == "__main__":
    residual_thresh = 1.5
    good_bead_bad_bead_ratio_thresh = 0.5
    nbeads_thresh = 40
    ncpu = args.ncpu
    bead_path = args.bead_path
    md_path = args.md_path
    out_path = args.out_path
    if isinstance(ncpu, list):
        assert(len(ncpu)==1)
        ncpu = ncpu[0]
    bead_dicts = pickle.load(open(bead_path, 'rb'))
    md = Metadata(md_path)
    posnames = md.posnames
    base_path = md.base_pth
    if not base_path[-1]=='/':
        base_path=base_path+'/'
    chunksize=1
    os.environ['MKL_NUM_THREADS'] = '2'
    os.environ['GOTO_NUM_THREADS'] = '2'
    os.environ['OMP_NUM_THREADS'] = '2'
    out_path = out_path
    #print(out_path)
    pfunc_xcorr = partial(wrappadappa_bead_xcorr, md_pth=md_path)
    with multiprocessing.Pool(ncpu) as ppool:
        results = ppool.map(pfunc_xcorr, posnames)
        seed_tforms = {p:k for p,k in results}
        func_inputs = [(bead_dicts[p], seed_tforms[p]) for p in posnames]
        results = ppool.starmap(optimize_tforms, func_inputs)
        good_positions = {}
        bad_positions = {}
        r = []
        n = []
        q = []
        results = [t for t in results if not t=='Error']
        for pos, (tvec, quals) in zip(posnames, results):
            residuals = [i['residual'] for i in quals.values()]
            nbeads = [i['nbeads'] for i in quals.values()]
            ratio = [i['bead_outlier_ratio'] for i in quals.values()]
            bead_dists = [i['all_bead_dists'] for i in quals.values()]
            accepted_bead_dists = [i['accepted_bead_dists'] for i in quals.values()]
            r += residuals
            n += nbeads
            q += ratio
            if np.amax(residuals) > residual_thresh:
                bad_positions[pos] = (tvec, quals)
                continue
            if np.amin(nbeads) < nbeads_thresh and (np.amin(ratio) < good_bead_bad_bead_ratio_thresh):
                bad_positions[pos] = (tvec, quals)
                continue
            good_positions[pos] = (tvec, quals)
        gposnames = list(good_positions.keys())
        #pickle.dump(good_positions, open(os.path.join(out_path, 'tforms.pkl'), 'wb'))
        pickle.dump({'good': good_positions, 'bad': bad_positions}, open(out_path, 'wb'))
    print('Number good positoins: ', len(good_positions))