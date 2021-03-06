from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.grid_search import ParameterGrid
from sklearn.metrics import log_loss
from functions import *
from sklearn.decomposition import PCA, KernelPCA

target_col = 'target'

""" Load data and change into used format"""
print('Load data')
train_raw = pd.read_csv("numerai_training_data.csv")
target = train_raw[target_col]
print(target.value_counts(normalize=True))
train_raw = np.array(train_raw.drop(target_col, axis=1))

test_raw = pd.read_csv("numerai_tournament_data.csv")
test_results = test_raw['t_id']
test_results.index = test_raw['t_id']
test_results = pd.DataFrame(test_results)
test_results['probability'] = np.zeros((test_raw.shape[0]))
del test_results['t_id']
del test_raw['t_id']
test_raw = np.array(test_raw)
print(test_results)

print(train_raw.shape)
print(test_raw.shape)

inter_m = [[0, 7], [2, 17], [3, 13], [6, 8], [6, 11], [7, 18], [9, 10], [9, 20], [10, 20], [12, 14], [14, 15], [16, 19]]
train_m_features = np.zeros((train_raw.shape[0], len(inter_m)))
test_m_features = np.zeros((test_raw.shape[0], len(inter_m)))
for i, int_features in enumerate(inter_m):
    train_m_features[:, i] = train_raw[:, int_features[0]] - train_raw[:, int_features[1]]
    test_m_features[:, i] = test_raw[:, int_features[0]] - test_raw[:, int_features[1]]

"""
CV
"""
best_score = 10
best_params = 0
best_train_prediction = 0
best_prediction = 0
meta_solvers_train = []
meta_solvers_test = []
best_train = 0
best_test = 0

param_grid = [
              {'eval_metric': ['logloss'],
               'eta': [0.003],
               'objective': ['binary:logistic'],
               'max_depth': [6],
               'num_round': [5000],
               'subsample': [0.75],
               'metric_feature_lim': [0],
               'n_monte_carlo': [5],
               'cv_n': [5],
               'test_rounds_fac': [1.2],
               'count_n': [0],
               'mc_test': [True],
               'pca_n': [5]
               }
              ]

lda = LinearDiscriminantAnalysis()
print('start CV')
early_stopping = 120
mc_logloss_mean = []
mc_logloss_sd = []
params_list = []
print_results = []
for params in ParameterGrid(param_grid):
    print(params)
    params_list.append(params)

    train_predictions = np.ones((train_raw.shape[0],))

    pcaing = PCA(n_components=params['pca_n'])

    # train_pca = pcaing.fit_transform(train_raw)
    # test_pca = pcaing.transform(test_raw)
    # print(pcaing.explained_variance_ratio_)
    #
    # train = np.hstack(tuple([train_raw, train_pca, train_m_features]))
    # test = np.hstack(tuple([test_raw, test_pca, test_m_features]))

    train = train_raw
    test = test_raw
    print('There are %d columns' % train.shape[1])

    # CV
    mc_logloss = []
    mc_train_pred = []
    for i_mc in range(params['n_monte_carlo']):
        cv_n = params['cv_n']
        kf = StratifiedKFold(target.values, n_folds=cv_n, shuffle=True, random_state=i_mc ** 3)

        xgboost_rounds = []

        for cv_train_index, cv_test_index in kf:
            X_train, X_test = train[cv_train_index, :], train[cv_test_index, :]
            y_train, y_test = target.iloc[cv_train_index].values, target.iloc[cv_test_index].values

            lda.fit(X_train, y_train)

            # predict
            predicted_results = lda.predict_proba(X_test)[:, 1]
            train_predictions[cv_test_index] = predicted_results

        print('logloss score ', log_loss(target.values, train_predictions))
        mc_logloss.append(log_loss(target.values, train_predictions))
        mc_train_pred.append(train_predictions)

    mc_train_pred = np.mean(np.array(mc_train_pred), axis=0)

    mc_logloss_mean.append(np.mean(mc_logloss))
    mc_logloss_sd.append(np.std(mc_logloss))
    print('The Logloss range is: %.5f to %.5f' %
          (mc_logloss_mean[-1] - mc_logloss_sd[-1], mc_logloss_mean[-1] + mc_logloss_sd[-1]))
    print_results.append('The AUC range is: %.5f to %.5f' %
                         (mc_logloss_mean[-1] - mc_logloss_sd[-1], mc_logloss_mean[-1] + mc_logloss_sd[-1]))
    print('For ', mc_logloss)
    print('The AUC of the average prediction is: %.5f' % log_loss(target.values, mc_train_pred))
    meta_solvers_train.append(mc_train_pred)

    if params['mc_test']:

        mc_pred = []
        for i_mc in range(params['n_monte_carlo']):
            params['seed'] = i_mc

            lda.fit(train, target.values)
            mc_pred.append(lda.predict_proba(test)[:, 1])

        meta_solvers_test.append(np.mean(np.array(mc_pred), axis=0))

    if mc_logloss_mean[-1] < best_score:
        print('new best log loss')
        best_score = mc_logloss_mean[-1]
        best_params = params
        best_train_prediction = mc_train_pred
        if params['mc_test']:
            best_prediction = meta_solvers_test[-1]

print(best_score)
print(best_params)

print(params_list)
print(print_results)
print(mc_logloss_mean)
print(mc_logloss_sd)
"""
Final Solution
"""
""" Write opt solution """
if best_params['mc_test']:
    print('writing to file')
    print(best_prediction)
    pd.DataFrame(best_train_prediction).to_csv('train_lda.csv')
    test_results['probability'] = best_prediction
    test_results.to_csv("test_lda.csv")

""" n_monte_carlo = 5, CV = 5 """
# raw dataset: 0.6915/ 0.

