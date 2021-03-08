"""Utilities"""

import numpy as np
import sklearn.decomposition._nmf as sknmf
from sklearn.metrics import pairwise_distances
from scipy.optimize import linear_sum_assignment
import itertools
import scipy as sp
from operator import itemgetter

##################
# Useful globals #
##################

trinucleotides_C = ["ACA",
                    "ACC",
                    "ACG",
                    "ACT",
                    "CCA",
                    "CCC",
                    "CCG",
                    "CCT",
                    "GCA",
                    "GCC",
                    "GCG",
                    "GCT",
                    "TCA",
                    "TCC",
                    "TCG",
                    "TCT"]

trinucleotides_T = ["ATA",
                    "ATC",
                    "ATG",
                    "ATT",
                    "CTA",
                    "CTC",
                    "CTG",
                    "CTT",
                    "GTA",
                    "GTC",
                    "GTG",
                    "GTT",
                    "TTA",
                    "TTC",
                    "TTG",
                    "TTT"]

snv_types_6_str = ["C>A", "C>G", "C>T", "T>A", "T>C", "T>G"]

snv_types_6_set = [{"C", "A"}, {"C", "G"}, {"C", "T"},
                   {"T", "A"}, {"T", "C"}, {"T", "G"}]

snv_types_96_str = (["C>A" + ":" + item for item in trinucleotides_C] +
                    ["C>G" + ":" + item for item in trinucleotides_C] +
                    ["C>T" + ":" + item for item in trinucleotides_C] +
                    ["T>A" + ":" + item for item in trinucleotides_T] +
                    ["T>C" + ":" + item for item in trinucleotides_T] +
                    ["T>G" + ":" + item for item in trinucleotides_T])

snv_types_96_list = ([["C>A", item] for item in trinucleotides_C] +
                     [["C>G", item] for item in trinucleotides_C] +
                     [["C>T", item] for item in trinucleotides_C] +
                     [["T>A", item] for item in trinucleotides_T] +
                     [["T>C", item] for item in trinucleotides_T] +
                     [["T>G", item] for item in trinucleotides_T])


#####################
# Utility functions #
#####################

def beta_divergence_deprecated(A, B, beta=1, square_root=False):
    """Beta_divergence

    A and B must be float arrays.

    DEPRECATED
    ----------
    sknmf._beta_divergence has problems when beta = 1. The problem seems to be in the following line:
    sum_WH = np.dot(np.sum(W, axis=0), np.sum(H, axis=1)),
    together with the fact that it takes 3 separate matrix sums and then do the additions. That results
    in reduced accuracy in small differences, which is really what matters for the final result. Basically,
    KL divergence is \sum(Alog(A/B) - A + B). If you do \sum(Alog(A/B)) - \sum(A) + \sum(B), it'll be less
    accurate.
    Note that using the aux matrix as in this function seems better than using sknmf._beta_divergence alone.
    But we should not use this function anyway.
    """
    aux = np.diag(np.ones(B.shape[1])).astype(float)
    return sknmf._beta_divergence(A, B, aux, beta=beta, square_root=square_root)


def beta_divergence(A, B, beta=1, square_root=False):
    """Beta_divergence

    A and B must be float arrays.

    Notes
    ----------
    For KL divergence, we do not deal with the case where B_ij = 0 but A_ij != 0,
    i.e., we'll output inf if that happens.
    For the purpose of NMF, B_ij will never be 0, because within the NMF algorithm,
    we always clip small values. So 0's will be replaced by EPSILON in W and H. As
    a result, W @ H will never have 0 entries.
    """
    if beta == 1 or beta == "kullback-leibler":
        # When B_ij = 0, KL divergence is not defined unless A_ij = 0.
        # Whenever A_ij = 0, then the contribution of the term A_ij log(A_ij/B_ij)
        # is considered as 0.
        A_data = A.ravel()
        B_data = B.ravel()
        indices = A_data > 0
        A_data = A_data[indices]
        B_data_remaining = B_data[~indices]
        B_data = B_data[indices]
        # Here we must take matrix additions first and then take sum.
        # Otherwise, the separate matrix sums will be too big and the small
        # differences will be lost, and we'll get 0.0 results.
        res = np.sum(A_data*np.log(A_data/B_data) - A_data + B_data)
        res = res + np.sum(B_data_remaining)
    else:
        raise ValueError('Only beta = 1 is implemented.')
    if square_root:
        res = np.sqrt(2*res)

    return res


def normalize_WH(W, H):
    normalization_factor = np.sum(W, 0)
    return W/normalization_factor, H*normalization_factor[:, None]


def match_catalog_pair(W1, W2, metric='cosine'):
    """Match a pair of signature catalogs.

    Notes
    ----------
    1. Assume a 1-to-1 match between H1 and H2. This is an assignment problem
    (See https://en.wikipedia.org/wiki/Assignment_problem).
    2. W2 will be reordered to match with W1.
    """
    if W1.shape != W2.shape:
        raise ValueError('W1 and W2 must be of the same shape.')

    pdist = pairwise_distances(W1.T, W2.T, metric=metric)
    W2_reordered_indices = linear_sum_assignment(pdist)[1]
    return W2[:, W2_reordered_indices], W2_reordered_indices


def simulate_count_matrix(W, H, method='multinomial'):
    n_features, n_components = W.shape
    _, n_samples = H.shape

    # Just in case W and H are not properly normalized
    W, H = normalize_WH(W, H)

    if method == 'multinomial':
        X_simulated = []
        for h in H.T:
            x = np.zeros(n_features, dtype=int)
            for i in range(0, n_components):
                N = int(round(h[i]))
                indices = np.random.choice(n_features, size=N, replace=True, p=W[:, i])
                x += np.array([np.sum(indices == j) for j in range(0, n_features)])
            X_simulated.append(x)
        X_simulated = np.array(X_simulated).T
    else:
        raise ValueError(
            'Invalid method parameter: got %r instead of one of %r' %
            (method, {'multinomial'}))

    return X_simulated


def bootstrap_count_matrix(X):
    n_features, n_samples = X.shape
    X_bootstrapped = []
    for x in X.T:
        N = int(round(np.sum(x)))
        indices = np.random.choice(n_features, size=N, replace=True, p=x/N)
        X_bootstrapped.append([np.sum(indices == i)
                               for i in range(0, n_features)])
    X_bootstrapped = np.array(X_bootstrapped).T
    return X_bootstrapped


def _samplewise_error(X, X_reconstructed):
    errors = []
    for x, x_reconstructed in zip(X.T, X_reconstructed.T):
        errors.append(beta_divergence(x, x_reconstructed, beta=1, square_root=False))
    errors = np.array(errors)
    return errors


def match_signature_to_catalog(w, W_catalog, thresh=0.99, include_top=True):
    """Match a single signature to possibly multiple signatures in the catalog.

    Parameters
    ----------
    w : array-like of shape (n_features,)
        The signature to be matched.

    W_catalog : array-like of shape (n_features, n_sigs).
        The signature catalog.

    thresh : float
        If cosine similarity to any signature in W_catalog is >= thresh, then w is matched to that signature.
        If cosine similarity to all signatures in W_catalog is < thresh, then doublets will be considered.
        If cosine similarity to any doublet is >= thresh, then w is matched to that doublet.
        If cosine similarity to all doublets is < thresh, then triplets will be considered.

    include_top : bool
        If true, then the top matched signature will always be included when doublets or triplets are considered.
        Otherwise, all possible doublets or triplets will be considered when applicable.


    Returns
    ----------
    match : tuple
        Index/indices of matched signature(s).

    cos : float
        Cosine similarity.

    coef : array-like or None
        When w is matched to doublets or triplets, coef is the NNLS coef for reconstructing w.
        When w is matched to a single signature, coef is None.
    """
    n_features, n_sigs = W_catalog.shape
    ###################################################
    ###################### Singles ####################
    ###################################################
    ### Calculate cosine similarity to each signature in the catalog
    data = []
    for i, w_catalog in zip(range(0, n_sigs), W_catalog.T):
        data.append([i, 1 - sp.spatial.distance.cosine(w, w_catalog)])
    data = sorted(data, key=itemgetter(1), reverse=True)
    match = (data[0][0],)
    cos = data[0][1]
    coef = None
    # If the top matched signature has cosine similarity >= thresh, then return this signature.
    if cos >= thresh:
        return match, cos, coef

    ###################################################
    ##################### Doublets ####################
    ###################################################
    ### Otherwise, consider doublets
    # First, construct the combinations of signatures to be tested.
    sigs = range(0, n_sigs) # Indices of all signatures in the catalog.
    top = data[0][0] # Index of the top matched signature.
    combs = [] # All signature combinations to be tested.
    if include_top:
        sigs_notop = [sig for sig in sigs if sig != top] # Indices of all signatures excluding the top matched signature.
        combs.extend([(top, sig) for sig in sigs_notop])
    else:
        combs.extend(list(itertools.combinations(sigs, 2)))
    # Then, perform NNLS on all combinations to be tested, and select the best combination based on residual error.
    data = []
    for item in combs:
        x, resid = sp.optimize.nnls(W_catalog[:, list(item)], w)
        data.append([item, x, resid])
    data = sorted(data, key=itemgetter(2))
    match = data[0][0]
    coef = data[0][1]
    cos = 1 - sp.spatial.distance.cosine(w, np.dot(W_catalog[:, list(match)], coef))
    # If cosine similarity >= thresh, return the best doublet
    if cos >= thresh:
        return match, cos, coef

    ###################################################
    ##################### Triplets ####################
    ###################################################
    ### Otherwise, consider triplets
    combs = []
    if include_top:
        sigs_notop = [sig for sig in sigs if sig != top] # Indices of all signatures excluding the top matched signature.
        combs.extend([(top,) + item for item in list(itertools.combinations(sigs_notop, 2))])
    else:
        combs.extend(list(itertools.combinations(sigs, 3)))
    data = []
    for item in combs:
        x, resid = sp.optimize.nnls(W_catalog[:, list(item)], w)
        data.append([item, x, resid])
    data = sorted(data, key=itemgetter(2))
    match = data[0][0]
    coef = data[0][1]
    cos = 1 - sp.spatial.distance.cosine(w, np.dot(W_catalog[:, list(match)], coef))
    return match, cos, coef
