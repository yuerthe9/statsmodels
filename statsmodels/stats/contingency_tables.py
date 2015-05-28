"""
Methods for analyzing contingency tables.
"""

from __future__ import division
from statsmodels.tools.decorators import cache_readonly, resettable_cache
import numpy as np
from scipy import stats
import pandas as pd
from statsmodels import iolib

def _handle_pandas_square(table):
    """
    Reindex a pandas table so that it becomes square (extending the
    row and column index as needed).
    """

    if not isinstance(table, pd.DataFrame):
        return table

    # If the table is not square, make it square
    if table.shape[0] != table.shape[1]:
        ix = list(set(table.index) | set(table.columns))
        table = table.reindex(ix, axis=0)
        table = table.reindex(ix, axis=1)

    return table

class _bunch(object):
    pass


class TableSymmetry(object):
    """
    Methods for analyzing a square contingency table.

    Parameters
    ----------
    table : array-like
        A contingency table.

    These methods should only be used when the rows and columns of the
    table have the same categories.  If `table` is provided as a
    Pandas array, the row and column indices will be extended to
    create a scquare table.  Otherwise the table should be provided in
    a square form, with the rows and columns in the same order.
    """

    def __init__(self, table):
        table = _handle_pandas_square(table)
        table = np.asarray(table, dtype=np.float64)
        k, k2 = table.shape
        if k != k2:
            raise ValueError('table must be square')
        self._table = table


    @classmethod
    def from_data(cls, data):
        """
        Construct a TableSymmetry object from data.

        Parameters
        ----------
        data : array-like
            The raw data, from which a cross-table is constructed
            using the first two columns.

        Returns
        -------
        A TableSymmetry instance.
        """

        if isinstance(data, pd.DataFrame):
            table = pd.crosstab(data.iloc[:, 0], data.iloc[:, 1])
        else:
            table = pd.crosstab(data[:, 0], data[:, 1])

        return cls(table)


    def symmetry(self, method="bowker"):
        """
        Test for symmetry of a joint distribution.

        This procedure tests the null hypothesis that the joint
        distribution is symmetric around the main diagonal, that is

        .. math::

        p_{i, j} = p_{j, i}  for all i, j

        Returns
        -------
        statistic : float
            chisquare test statistic
        p-value : float
            p-value of the test statistic based on chisquare distribution
        df : int
            degrees of freedom of the chisquare distribution

        Notes
        -----
        The implementation is based on the SAS documentation. R includes
        it in `mcnemar.test` if the table is not 2 by 2.  However a more
        direct generalization of the McNemar test to large tables is
        provided by the homogeneity test (TableSymmetry.homogeneity).

        The p-value is based on the chi-square distribution which requires
        that the sample size is not very small to be a good approximation
        of the true distribution. For 2x2 contingency tables the exact
        distribution can be obtained with `mcnemar`

        See Also
        --------
        mcnemar
        homogeneity
        """

        if method.lower() != "bowker":
            raise ValueError("method for symmetry testing must be 'bowker'")

        k = self._table.shape[0]
        upp_idx = np.triu_indices(k, 1)

        tril = self._table.T[upp_idx]   # lower triangle in column order
        triu = self._table[upp_idx]     # upper triangle in row order

        stat = ((tril - triu)**2 / (tril + triu + 1e-20)).sum()
        df = k * (k-1) / 2.
        pval = stats.chi2.sf(stat, df)

        return stat, pval, df


    def homogeneity(self, method="stuart_maxwell"):
        """
        Compare row and column marginal distributions.

        Parameters
        ----------
        method : string
            Either 'stuart_maxwell' or 'bhapkar', leading to two different
            estimates of the covariance matrix for the estimated
            difference between the row margins and the column margins.

        Returns
        -------
        stat : float
            The chi^2 test statistic
        pvalue : float
            The p-value of the test statistic
        df : integer
            The degrees of freedom of the reference distribution

        Notes
        -----
        For a 2x2 table this is equivalent to McNemar's test.  More
        generally the procedure tests the null hypothesis that the
        marginal distribution of the row factor is equal to the marginal
        distribution of the column factor.  For this to be meaningful, the
        two factors must have the same sample space.
        """

        if self._table.shape[0] < 1:
            raise ValueError('table is empty')
        elif self._table.shape[0] == 1:
            return 0., 1., 0

        method = method.lower()
        if method not in ["bhapkar", "stuart_maxwell"]:
            raise ValueError("method '%s' for homogeneity not known" % method)

        n_obs = self._table.sum()
        pr = self._table.astype(np.float64) / n_obs

        # Compute margins, eliminate last row/column so there is no
        # degeneracy
        row = pr.sum(1)[0:-1]
        col = pr.sum(0)[0:-1]
        pr = pr[0:-1, 0:-1]

        # The estimated difference between row and column margins.
        d = col - row

        # The degrees of freedom of the chi^2 reference distribution.
        df = pr.shape[0]

        if method == "bhapkar":
            vmat = -(pr + pr.T) - np.outer(d, d)
            dv = col + row - 2*np.diag(pr) - d**2
            np.fill_diagonal(vmat, dv)
        elif method == "stuart_maxwell":
            vmat = -(pr + pr.T)
            dv = row + col - 2*np.diag(pr)
            np.fill_diagonal(vmat, dv)

        try:
            stat = n_obs * np.dot(d, np.linalg.solve(vmat, d))
        except np.linalg.LinAlgError:
            warnings.warn("Unable to invert covariance matrix")
            return np.nan, np.nan, df

        pvalue = 1 - stats.chi2.cdf(stat, df)

        return stat, pvalue, df


    def summary(self, alpha=0.05):

        headers = ["Statistic", "P-value", "DF"]
        stubs = ["Symmetry", "Homogeneity"]
        stat1, pvalue1, df1 = self.symmetry()
        stat2, pvalue2, df2 = self.homogeneity()
        data = [['%.3f' % stat1, '%.3f' % pvalue1, '%d' % df1],
                ['%.3f' % stat2, '%.3f' % pvalue2, '%d' % df2]]
        tab = iolib.SimpleTable(data, headers, stubs, data_aligns="r",
                                 table_dec_above='')

        return tab


def ordinal_association(table, row_scores=None, col_scores=None, method="lbl",
                        return_object=True):
    """
    Assess row/column association in a table with ordinal rows/columns.

    Parameters
    ----------
    table : array-like
        A contingency table.
    row_scores : array-like
        Scores used to weight the rows, defaults to 0, 1, ...
    col_scores : array-like
        Scores used to weight the columns, defaults to 0, 1, ...
    method : string
        Only 'lbl' (Agresti's 'linear by linear' method) is implemented.
    return_object : bool
        If True, return an object containing test results.

    Returns
    -------
    If `return_object` is False, returns the z-score and the p-value
    obtained from the normal distribution.  Otherwise returns a bunch
    containing the test statistic, its null mean and standard
    deviation, the corresponding Z-score, degrees of freedom, and
    p-value.

    Notes
    -----
    Using the default row and column scores gives the Cochran-Armitage
    trend test.

    To assess association in a table with nominal row and column
    factors, a Pearson chi^2 test can be used.
    """

    table = np.asarray(table, dtype=np.float64)

    method = method.lower()
    if method != "lbl":
        raise ValueError("method for asociation must be 'lbl'")

    # Set defaults if needed.
    if row_scores is None:
        row_scores = np.arange(table.shape[0])
    if col_scores is None:
        col_scores = np.arange(table.shape[1])

    if len(row_scores) != table.shape[0]:
        raise ValueError("The length of `row_scores` must match the first dimension of `table`.")

    if len(col_scores) != table.shape[1]:
        raise ValueError("The length of `col_scores` must match the second dimension of `table`.")

    # The test statistic
    stat = np.dot(row_scores, np.dot(table, col_scores))

    # Some needed quantities
    n_obs = table.sum()
    rtot = table.sum(1)
    um = np.dot(row_scores, rtot)
    u2m = np.dot(row_scores**2, rtot)
    ctot = table.sum(0)
    vn = np.dot(col_scores, ctot)
    v2n = np.dot(col_scores**2, ctot)

    # The null mean and variance of the test statistic
    e_stat = um * vn / n_obs
    v_stat = (u2m - um**2 / n_obs) * (v2n - vn**2 / n_obs) / (n_obs - 1)
    sd_stat = np.sqrt(v_stat)

    zscore = (stat - e_stat) / sd_stat
    pvalue = 2 * stats.norm.cdf(-np.abs(zscore))

    if return_object:
        b = _bunch()
        b.stat = stat
        b.stat_e0 = e_stat
        b.stat_sd0 = sd_stat
        b.zscore = zscore
        b.pvalue = pvalue
        return b

    return zscore, pvalue


class StratifiedTables(object):
    """
    Analyses for a collection of 2x2 stratified contingency tables.

    This class implements the 'Cochran-Mantel-Haenszel' and
    'Breslow-Day' procedures for analyzing collections of 2x2
    contingency tables.

    Parameters
    ----------
    tables : list
        A list containing 2x2 contingency tables.
    """

    def __init__(self, tables, shift_zeros=False):

        # Create a data cube
        tables = [np.asarray(x) for x in tables]
        table = [x[:, :, None] for x in tables]
        table = np.concatenate(table, axis=2).astype(np.float64)

        if shift_zeros:
            zx = (table == 0).sum(0).sum(0)
            ix = np.flatnonzero(zx > 0)
            if len(ix) > 0:
                table[:, :, ix] += 0.5

        self._table = table

        self._cache = resettable_cache()

        # Quantities to precompute.  Table entries are [[a, b], [c,
        # d]], 'ad' is 'a * d', 'apb' is 'a + b', 'dma' is 'd - a',
        # etc.
        self._apb = table[0, 0, :] + table[0, 1, :]
        self._apc = table[0, 0, :] + table[1, 0, :]
        self._bpd = table[0, 1, :] + table[1, 1, :]
        self._cpd = table[1, 0, :] + table[1, 1, :]
        self._ad = table[0, 0, :] * table[1, 1, :]
        self._bc = table[0, 1, :] * table[1, 0, :]
        self._apd = table[0, 0, :] + table[1, 1, :]
        self._dma = table[1, 1, :] - table[0, 0, :]
        self._n = table.sum(0).sum(0)


    @classmethod
    def from_data(cls, var1, var2, strata, data):
        """
        Construct a StratifiedTables object from data.

        Parameters
        ----------
        var1 : int or string
            The column index or name of `data` containing the variable
            defining the rows of the contingency table.  The variable
            must have only two distinct values.
        var2 : int or string
            The column index or name of `data` containing the variable
            defining the columns of the contingency table.  The variable
            must have only two distinct values.
        strata : int or string
            The column index of name of `data` containing the variable
            defining the strata.
        data : array-like
            The raw data.  A cross-table for analysis is constructed
            from the first two columns.

        Returns
        -------
        A StratifiedTables instance.
        """

        if not isinstance(data, pd.DataFrame):
            data1 = pd.DataFrame(index=data.index, column=[var1, var2, strata])
            data1.loc[:, var1] = data[:, var1]
            data1.loc[:, var2] = data[:, var2]
            data1.loc[:, strata] = data[:, strata]
        else:
            data1 = data

        gb = data1.groupby(strata).groups
        tables = []
        for g in gb:
            ii = gb[g]
            tab = pd.crosstab(data1.loc[ii, var1], data1.loc[ii, var2])
            tables.append(tab)
        return cls(tables)


    def test_null_odds(self, correction=False):
        """
        Test that all tables have odds ratio = 1.

        This is the 'Mantel-Haenszel' test.

        Parameters
        ----------
        correction : boolean
            If True, use the continuity correction when calculating the
            test statistic.

        Returns the chi^2 test statistic and p-value.
        """

        stat = np.sum(self._table[0, 0, :] - self._apb * self._apc / self._n)
        stat = np.abs(stat)
        if correction:
            stat -= 0.5
        stat = stat**2
        denom = self._apb * self._apc * self._bpd * self._cpd
        denom /= (self._n**2 * (self._n - 1))
        denom = np.sum(denom)
        stat /= denom

        # df is always 1
        pvalue = 1 - stats.chi2.cdf(stat, 1)

        return stat, pvalue


    @cache_readonly
    def common_odds(self):
        """
        An estimate of the common odds ratio.

        This is the Mantel-Haenszel estimate of a odds ratio that is
        common to all tables.
        """

        odds_ratio = np.sum(self._ad / self._n) / np.sum(self._bc / self._n)
        return odds_ratio


    @cache_readonly
    def common_logodds(self):
        """
        An estimate of the common log odds ratio.

        This is the Mantel-Haenszel estimate of a risk ratio that is
        common to all tables.
        """

        return np.log(self.common_odds)


    @cache_readonly
    def common_risk(self):
        """
        An estimate of the common risk ratio.

        This is an estimate of a risk ratio that is common to all
        tables.
        """

        acd = self._table[0, 0, :] * self._cpd
        cab = self._table[1, 0, :] * self._apb

        risk_ratio = np.sum(acd / self._n) / np.sum(cab / self._n)
        return risk_ratio


    @cache_readonly
    def common_logodds_se(self):
        """
        Returns the estimated standard error of the common log odds ratio.

        References
        ----------
        Robins, Breslow and Greenland (Biometrics, 42:311–323)
        """

        adns = np.sum(self._ad / self._n)
        bcns = np.sum(self._bc / self._n)
        lor_va = np.sum(self._apd * self._ad / self._n**2) / adns**2
        mid = self._apd * self._bc / self._n**2
        mid += (1 - self._apd / self._n) * self._ad / self._n
        mid = np.sum(mid)
        mid /= (adns * bcns)
        lor_va += mid
        lor_va += np.sum((1 - self._apd / self._n) * self._bc / self._n) / bcns**2
        lor_va /= 2
        lor_se = np.sqrt(lor_va)
        return lor_se


    def common_logodds_confint(self, alpha=0.05):
        """
        A confidence interval for the common log odds ratio.

        Parameters
        ----------
        alpha : float
            `1 - alpha` is the nominal coverage probability of the
            interval.

        Returns
        -------
        lcb : float
            The lower confidence limit.
        ucb : float
            The upper confidence limit.
        """

        lor = np.log(self.common_odds)
        lor_se = self.common_logodds_se

        f = -stats.norm.ppf(alpha / 2)

        lcb = lor - f * lor_se
        ucb = lor + f * lor_se

        return lcb, ucb


    def common_odds_confint(self, alpha=0.05):
        """
        A confidence interval for the common odds ratio.

        Parameters
        ----------
        alpha : float
            `1 - alpha` is the nominal coverage probability of the
            interval.

        Returns
        -------
        lcb : float
            The lower confidence limit.
        ucb : float
            The upper confidence limit.
        """

        lcb, ucb = self.common_logodds_confint(alpha)
        lcb = np.exp(lcb)
        ucb = np.exp(ucb)
        return lcb, ucb


    def test_equal_odds(self, adjust=False):
        """
        Test that all odds ratios are identical.

        This is the 'Breslow-Day' testing procedure.

        Parameters
        ----------
        adjust : boolean
            Use the 'Tarone' adjustment to achieve the correct
            asymptotic distribution.

        Returns the test statistic and p-value.
        """

        table = self._table

        r = self.common_odds
        a = 1 - r
        b = r * (self._apb + self._apc) + self._dma
        c = -r * self._apb * self._apc

        # Expected value of first cell
        e11 = (-b + np.sqrt(b**2 - 4*a*c)) / (2*a)

        # Variance of the first cell
        v11 = 1 / e11 + 1 / (self._apc - e11) + 1 / (self._apb - e11) + 1 / (self._dma + e11)
        v11 = 1 / v11

        stat = np.sum((table[0, 0, :] - e11)**2 / v11)

        if adjust:
            adj = table[0, 0, :].sum() - e11.sum()
            adj = adj**2
            adj /= np.sum(v11)
            stat -= adj

        pvalue = 1 - stats.chi2.cdf(stat, table.shape[2] - 1)

        return stat, pvalue


    def summary(self, alpha=0.05):

        def fmt(x):
            if type(x) is str:
                return x
            return "%.3f" % x

        co_lcb, co_ucb = self.common_odds_confint(alpha=alpha)
        clo_lcb, clo_ucb = self.common_logodds_confint(alpha=alpha)
        headers = ["Estimate", "LCB", "UCB"]
        stubs = ["Common odds", "Common log odds", "Common risk ratio", ""]
        data = [[fmt(x) for x in [self.common_odds, co_lcb, co_ucb]],
                [fmt(x) for x in [self.common_logodds, clo_lcb, clo_ucb]],
                [fmt(x) for x in [self.common_risk, "", ""]],
                ['', '', '']]
        tab1 = iolib.SimpleTable(data, headers, stubs, data_aligns="r",
                                 table_dec_above='')

        headers = ["Statistic", "P-value", ""]
        stubs = ["Test of OR=1", "Test constant OR"]
        stat1, pvalue1 = self.test_null_odds()
        stat2, pvalue2 = self.test_equal_odds()
        data = [[fmt(x) for x in [stat1, pvalue1, ""]],
                [fmt(x) for x in [stat2, pvalue2, ""]]]
        tab2 = iolib.SimpleTable(data, headers, stubs, data_aligns="r")
        tab1.extend(tab2)

        headers = ["", "", ""]
        stubs = ["Number of tables", "Min n", "Max n", "Avg n", "Total n"]
        stat1, pvalue1 = self.test_null_odds()
        stat2, pvalue2 = self.test_equal_odds()
        ss = self._table.sum(0).sum(0)
        data = [["%d" % self._table.shape[2], '', ''],
                ["%d" % min(ss), '', ''],
                ["%d" % max(ss), '', ''],
                ["%.0f" % np.mean(ss), '', ''],
                ["%d" % sum(ss), '', '', '']]
        tab3 = iolib.SimpleTable(data, headers, stubs, data_aligns="r")
        tab1.extend(tab3)

        return tab1



def mcnemar(table, exact=True, correction=True):
    """
    McNemar test of homogeneity.

    Parameters
    ----------
    table : array-like
        A square contingency table.
    exact : bool
        If exact is true, then the binomial distribution will be used.
        If exact is false, then the chisquare distribution will be
        used, which is the approximation to the distribution of the
        test statistic for large sample sizes.
    correction : bool
        If true, then a continuity correction is used for the chisquare
        distribution (if exact is false.)

    Returns
    -------
    stat : float or int, array
        The test statistic is the chisquare statistic if exact is
        false. If the exact binomial distribution is used, then this
        contains the min(n1, n2), where n1, n2 are cases that are zero
        in one sample but one in the other sample.
    pvalue : float or array
        p-value of the null hypothesis of equal marginal distributions.

    Notes
    -----
    This is a special case of Cochran's Q test, and of the homogeneity
    test. The results when the chisquare distribution is used are
    identical, except for continuity correction.
    """

    table = _handle_pandas_square(table)
    table = np.asarray(table, dtype=np.float64)
    n1, n2 = table[0, 1], table[1, 0]

    if exact:
        stat = np.minimum(n1, n2)
        # binom is symmetric with p=0.5
        pval = stats.binom.cdf(stat, n1 + n2, 0.5) * 2
        pval = np.minimum(pval, 1)  # limit to 1 if n1==n2
    else:
        corr = int(correction) # convert bool to 0 or 1
        stat = (np.abs(n1 - n2) - corr)**2 / (1. * (n1 + n2))
        df = 1
        pval = stats.chi2.sf(stat, df)
    return stat, pval


def cochrans_q(x, return_object=True):
    """
    Cochran's Q test for identical binomial proportions.

    Parameters
    ----------
    x : array_like, 2d (N, k)
        data with N cases and k variables
    return_object : boolean
        Return values as bunch instead of as individual values.

    Returns
    -------
    Returns a bunch containing the following attributes, or the
    individual values according to the value of `return_object`.

    q_stat : float
       test statistic
    pvalue : float
       pvalue from the chisquare distribution

    Notes
    -----
    Cochran's Q is a k-sample extension of the McNemar test. If there
    are only two groups, then Cochran's Q test and the McNemar test
    are equivalent.

    The procedure tests that the probability of success is the same
    for every group.  The alternative hypothesis is that at least two
    groups have a different probability of success.

    In Wikipedia terminology, rows are blocks and columns are
    treatments.  The number of rows N, should be large for the
    chisquare distribution to be a good approximation.

    The Null hypothesis of the test is that all treatments have the
    same effect.

    References
    ----------
    http://en.wikipedia.org/wiki/Cochran_test
    SAS Manual for NPAR TESTS
    """

    x = np.asarray(x, dtype=np.float64)
    gruni = np.unique(x)
    N, k = x.shape
    count_row_success = (x == gruni[-1]).sum(1, float)
    count_col_success = (x == gruni[-1]).sum(0, float)
    count_row_ss = count_row_success.sum()
    count_col_ss = count_col_success.sum()
    assert count_row_ss == count_col_ss  #just a calculation check

    # From the SAS manual
    q_stat = (k-1) * (k *  np.sum(count_col_success**2) - count_col_ss**2) \
             / (k * count_row_ss - np.sum(count_row_success**2))

    # Note: the denominator looks just like k times the variance of
    # the columns

    # Wikipedia uses a different, but equivalent expression
    #q_stat = (k-1) * (k *  np.sum(count_row_success**2) - count_row_ss**2) \
    #         / (k * count_col_ss - np.sum(count_col_success**2))

    df = k - 1
    pvalue = stats.chi2.sf(q_stat, df)

    if return_object:
        b = _bunch()
        b.stat = q_stat
        b.df = df
        b.pvalue = pvalue
        return b

    return q_stat, pvalue, df
