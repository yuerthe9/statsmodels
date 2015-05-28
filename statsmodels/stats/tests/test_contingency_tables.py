"""
Tests for contingency table analyses.
"""

import numpy as np
import statsmodels.stats.contingency_tables as ctab
import pandas as pd
from numpy.testing import assert_allclose, assert_equal
import os
import statsmodels.api as sm

cur_dir = os.path.dirname(os.path.abspath(__file__))
fname = "contingency_table_r_results.csv"
fpath = os.path.join(cur_dir, 'results', fname)
r_results = pd.read_csv(fpath)


tables = [None, None, None]

tables[0] = np.asarray([[23, 15], [19, 31]])

tables[1] = np.asarray([[144, 33, 84, 126],
                        [2, 4, 14, 29],
                        [0, 2, 6, 25],
                        [0, 0, 1, 5]])

tables[2] = np.asarray([[20, 10, 5],
                        [3, 30, 15],
                        [0, 5, 40]])


def test_homogeneity():

    for k,table in enumerate(tables):
        st = sm.stats.TableSymmetry(table)
        stat, pvalue, df = st.homogeneity()
        assert_allclose(stat, r_results.loc[k, "homog_stat"])
        assert_allclose(df, r_results.loc[k, "homog_df"])

        # Test Bhapkar via its relationship to Stuart_Maxwell.
        stat1, pvalue, df = st.homogeneity(method="bhapkar")
        assert_allclose(stat1, stat / (1 - stat / table.sum()))


def test_TableSymmetry_from_data():

    np.random.seed(434)
    df = pd.DataFrame(index=range(100), columns=["v1", "v2"])
    df["v1"] = np.random.randint(0, 5, 100)
    df["v2"] = np.random.randint(0, 5, 100)
    table = pd.crosstab(df["v1"], df["v2"])

    rslt1 = ctab.TableSymmetry(table)
    rslt2 = ctab.TableSymmetry.from_data(df)
    rslt3 = ctab.TableSymmetry(np.asarray(table))

    assert_equal(rslt1.summary().as_text(),
                 rslt2.summary().as_text())

    assert_equal(rslt2.summary().as_text(),
                 rslt3.summary().as_text())



def test_ordinal_association():

    for k,table in enumerate(tables):

        row_scores = 1 + np.arange(table.shape[0])
        col_scores = 1 + np.arange(table.shape[1])

        # First set of scores
        rslt = ctab.ordinal_association(table, row_scores,
                                        col_scores, return_object=True)
        assert_allclose(rslt.stat, r_results.loc[k, "lbl_stat"])
        assert_allclose(rslt.stat_e0, r_results.loc[k, "lbl_expval"])
        assert_allclose(rslt.stat_sd0**2, r_results.loc[k, "lbl_var"])
        assert_allclose(rslt.zscore**2, r_results.loc[k, "lbl_chi2"], rtol=1e-5, atol=1e-5)
        assert_allclose(rslt.pvalue, r_results.loc[k, "lbl_pvalue"], rtol=1e-5, atol=1e-5)

        # Second set of scores
        rslt = ctab.ordinal_association(table, row_scores,
                                        col_scores**2, return_object=True)
        assert_allclose(rslt.stat, r_results.loc[k, "lbl2_stat"])
        assert_allclose(rslt.stat_e0, r_results.loc[k, "lbl2_expval"])
        assert_allclose(rslt.stat_sd0**2, r_results.loc[k, "lbl2_var"])
        assert_allclose(rslt.zscore**2, r_results.loc[k, "lbl2_chi2"])
        assert_allclose(rslt.pvalue, r_results.loc[k, "lbl2_pvalue"], rtol=1e-5, atol=1e-5)


def test_symmetry():

    for k,table in enumerate(tables):
        st = sm.stats.TableSymmetry(table)
        stat, pvalue, df = st.symmetry()
        assert_allclose(stat, r_results.loc[k, "bowker_stat"])
        assert_equal(df, r_results.loc[k, "bowker_df"])
        assert_allclose(pvalue, r_results.loc[k, "bowker_pvalue"])


def test_mcnemar():

    # Use chi^2 without continuity correction
    stat1, pvalue1 = ctab.mcnemar(tables[0], exact=False,
                                  correction=False)

    st = sm.stats.TableSymmetry(tables[0])
    stat2, pvalue2, df = st.homogeneity()
    assert_allclose(stat1, stat2)
    assert_equal(df, 1)

    # Use chi^2 with continuity correction
    stat, pvalue = ctab.mcnemar(tables[0], exact=False,
                                correction=True)
    assert_allclose(pvalue, r_results.loc[0, "homog_cont_p"])

    # Use binomial reference distribution
    stat3, pvalue3 = ctab.mcnemar(tables[0], exact=True)
    assert_allclose(pvalue3, r_results.loc[0, "homog_binom_p"])


def test_cochranq():
    """
    library(CVST)
    table1 = matrix(c(1, 0, 1, 1,
                      0, 1, 1, 1,
                      1, 1, 1, 0,
                      0, 1, 0, 0,
                      0, 1, 0, 0,
                      1, 0, 1, 0,
                      0, 1, 0, 0,
                      1, 1, 1, 1,
                      0, 1, 0, 0), ncol=4, byrow=TRUE)
    rslt1 = cochranq.test(table1)
    table2 = matrix(c(0, 0, 1, 1, 0,
                      0, 1, 0, 1, 0,
                      0, 1, 1, 0, 1,
                      1, 0, 0, 0, 1,
                      1, 1, 0, 0, 0,
                      1, 0, 1, 0, 0,
                      0, 1, 0, 0, 0,
                      0, 0, 1, 1, 0,
                      0, 0, 0, 0, 0), ncol=5, byrow=TRUE)
    rslt2 = cochranq.test(table2)
    """

    table = [[1, 0, 1, 1],
             [0, 1, 1, 1],
             [1, 1, 1, 0],
             [0, 1, 0, 0],
             [0, 1, 0, 0],
             [1, 0, 1, 0],
             [0, 1, 0, 0],
             [1, 1, 1, 1],
             [0, 1, 0, 0]]
    table = np.asarray(table)

    stat, pvalue, df = ctab.cochrans_q(table, return_object=False)
    assert_allclose(stat, 4.2)
    assert_allclose(df, 3)

    table = [[0, 0, 1, 1, 0],
             [0, 1, 0, 1, 0],
             [0, 1, 1, 0, 1],
             [1, 0, 0, 0, 1],
             [1, 1, 0, 0, 0],
             [1, 0, 1, 0, 0],
             [0, 1, 0, 0, 0],
             [0, 0, 1, 1, 0],
             [0, 0, 0, 0, 0]]
    table = np.asarray(table)

    stat, pvalue, df = ctab.cochrans_q(table, return_object=False)
    assert_allclose(stat, 1.2174, rtol=1e-4)
    assert_allclose(df, 4)

    # Cochrane q and Mcnemar are equivalent for 2x2 tables
    data = table[:, 0:2]
    xtab = np.asarray(pd.crosstab(data[:, 0], data[:, 1]))
    stat1, pvalue1, df1 = ctab.cochrans_q(data, return_object=False)
    stat2, pvalue2 = ctab.mcnemar(xtab, exact=False, correction=False)
    assert_allclose(stat1, stat2)
    assert_allclose(pvalue1, pvalue2)



class CheckStratifiedMixin(object):

    def initialize(self, tables):
        self.rslt = ctab.StratifiedTables(tables)
        self.rslt_0 = ctab.StratifiedTables(tables, shift_zeros=True)
        tables_pandas = [pd.DataFrame(x) for x in tables]
        self.rslt_pandas = ctab.StratifiedTables(tables_pandas)


    def test_common_odds(self):
        assert_allclose(self.rslt.common_odds, self.common_odds,
                        rtol=1e-4, atol=1e-4)


    def test_common_logodds(self):
        assert_allclose(self.rslt.common_logodds, self.common_logodds,
                        rtol=1e-4, atol=1e-4)


    def test_null_odds(self):
        stat, pvalue = self.rslt.test_null_odds(correction=True)
        assert_allclose(stat, self.mh_stat, rtol=1e-4, atol=1e-5)
        assert_allclose(pvalue, self.mh_pvalue, rtol=1e-4, atol=1e-4)


    def test_common_odds_confint(self):
        lcb, ucb = self.rslt.common_odds_confint()
        assert_allclose(lcb, self.or_lcb, rtol=1e-4, atol=1e-4)
        assert_allclose(ucb, self.or_ucb, rtol=1e-4, atol=1e-4)


    def test_common_logodds_confint(self):
        lcb, ucb = self.rslt.common_logodds_confint()
        assert_allclose(lcb, np.log(self.or_lcb), rtol=1e-4,
                        atol=1e-4)
        assert_allclose(ucb, np.log(self.or_ucb), rtol=1e-4,
                        atol=1e-4)


    def test_equal_odds(self):

        if not hasattr(self, "or_homog"):
            return

        stat, pvalue = self.rslt_0.test_equal_odds()
        assert_allclose(stat, self.or_homog, rtol=1e-4, atol=1e-4)
        assert_allclose(pvalue, self.or_homog_p, rtol=1e-4, atol=1e-4)


    def test_pandas(self):

        assert_equal(self.rslt.summary().as_text(),
                     self.rslt_pandas.summary().as_text())


    def test_from_data(self):

        np.random.seed(241)
        df = pd.DataFrame(index=range(100), columns=("v1", "v2", "strat"))
        df["v1"] = np.random.randint(0, 2, 100)
        df["v2"] = np.random.randint(0, 2, 100)
        df["strat"] = np.kron(np.arange(10), np.ones(10))

        tables = []
        for k in range(10):
            ii = np.arange(10*k, 10*(k+1))
            tables.append(pd.crosstab(df.loc[ii, "v1"], df.loc[ii, "v2"]))

        rslt1 = ctab.StratifiedTables(tables)
        rslt2 = ctab.StratifiedTables.from_data("v1", "v2", "strat", df)

        assert_equal(rslt1.summary().as_text(), rslt2.summary().as_text())


class TestStratified1(CheckStratifiedMixin):
    """
    data = array(c(0, 0, 6, 5,
                   3, 0, 3, 6,
                   6, 2, 0, 4,
                   5, 6, 1, 0,
                   2, 5, 0, 0),
                   dim=c(2, 2, 5))
    rslt = mantelhaen.test(data)
    """

    def __init__(self):

        tables = [None] * 5
        tables[0] = np.array([[0, 0], [6, 5]])
        tables[1] = np.array([[3, 0], [3, 6]])
        tables[2] = np.array([[6, 2], [0, 4]])
        tables[3] = np.array([[5, 6], [1, 0]])
        tables[4] = np.array([[2, 5], [0, 0]])

        self.initialize(tables)

        self.common_odds = 7
        self.common_logodds = np.log(7)
        self.mh_stat = 3.9286
        self.mh_pvalue = 0.04747
        self.or_lcb = 1.026713
        self.or_ucb = 47.725133


class TestStratified2(CheckStratifiedMixin):
    """
    data = array(c(20, 14, 10, 24,
                   15, 12, 3, 15,
                   3, 2, 3, 2,
                   12, 3, 7, 5,
                   1, 0, 3, 2),
                   dim=c(2, 2, 5))
    rslt = mantelhaen.test(data)
    """

    def __init__(self):
        tables = [None] * 5
        tables[0] = np.array([[20, 14], [10, 24]])
        tables[1] = np.array([[15, 12], [3, 15]])
        tables[2] = np.array([[3, 2], [3, 2]])
        tables[3] = np.array([[12, 3], [7, 5]])
        tables[4] = np.array([[1, 0], [3, 2]])

        self.initialize(tables)

        self.common_odds = 3.5912
        self.common_logodds = np.log(3.5912)

        self.mh_stat = 11.8852
        self.mh_pvalue = 0.0005658

        self.or_lcb = 1.781135
        self.or_ucb = 7.240633


class TestStratified3(CheckStratifiedMixin):
    """
    data = array(c(313, 512, 19, 89,
                   207, 353, 8, 17,
                   205, 120, 391, 202,
                   278, 139, 244, 131,
                   138, 53, 299, 94,
                   351, 22, 317, 24),
                   dim=c(2, 2, 6))
    rslt = mantelhaen.test(data)
    """

    def __init__(self):

        tables = [None] * 6
        tables[0] = np.array([[313, 512], [19, 89]])
        tables[1] = np.array([[207, 353], [8, 17]])
        tables[2] = np.array([[205, 120], [391, 202]])
        tables[3] = np.array([[278, 139], [244, 131]])
        tables[4] = np.array([[138, 53], [299, 94]])
        tables[5] = np.array([[351, 22], [317, 24]])

        self.initialize(tables)

        self.common_odds = 1.101879
        self.common_logodds = np.log(1.101879)

        self.mh_stat = 1.3368
        self.mh_pvalue = 0.2476

        self.or_lcb = 0.9402012
        self.or_ucb = 1.2913602

        self.or_homog = 18.83297
        self.or_homog_p = 0.002064786
