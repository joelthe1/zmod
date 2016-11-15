import pandas as pd
import numpy as np
import xgboost
from sklearn import cross_validation
from sklearn.grid_search import GridSearchCV
from sklearn.metrics import accuracy_score, f1_score
from scipy.sparse import csr_matrix, hstack, vstack
import pickle
import sys
sys.path.insert(0, '/home/joelmathew89/zmod/bin/feature_engineering')
import lsa_and_clustering_on_raw_data as lsa
import pca_on_raw_data as pca_feats

class xgboost_wrapper:
    def __init__(self):
        self.X = None #stored as a CSR Matrix
        self.y = None #stored as an array
        self.X_dev = None
        self.y_dev = None
        self.X_test = None
        self.q_dict = None
        self.u_dict = None

        self.test_ids_dataframe = None

        self.model = None;
        self.train_info_dataframe = pd.read_csv("../../data/invited_info_train.txt", names = ['q_id','u_id','answered'], sep = '\t')

    def save_sparse_csr(self,filename,array):
        np.savez(filename,data = array.data ,indices=array.indices, indptr =array.indptr, shape=array.shape)

    def load_sparse_csr(self,filename):  
        loader = np.load(filename)
        return csr_matrix((  loader['data'], loader['indices'], loader['indptr']),shape = loader['shape'])

    # load data
    def load_data(self):
        print "\nLoading data from file..."
        self.X = self.load_sparse_csr("../../data/csr_mat_train_lsa.dat.npz").toarray()
        self.X_test = self.load_sparse_csr("../../data/csr_mat_test_lsa.dat.npz").toarray()
        self.y = pickle.load(open("../../data/csr_mat_train_y.pkl",'r'))
        self.test_ids_dataframe = pd.read_pickle("../../data/validate_nolabel.pkl")

#        test_size = 0.25
#        seed = 7
#        self.X, self.X_dev, self.y, self.y_dev = cross_validation.train_test_split(self.X, self.y, test_size=test_size, random_state=seed)
        print "Loading data from file(complete)..."

    def hot_load(self):
        print "\nHot load."
#        for i in range(5, 7, 1):
#            print '\nRunning for', str([i*100, i*100, i*10])
#            self.q_dict, self.u_dict = lsa.run([i*100, i*100, i*10])
#        
#            self.X = list()
#            tempX = list()
#            self.y = list()
#            print "\ncombining both user and question data..."
#            for idx, entry in self.train_info_dataframe.iterrows():
#                tempX.append(csr_matrix(hstack([self.q_dict[entry['q_id']], self.u_dict[entry['u_id']]])))
#                self.y.append(entry['answered'])

        self.q_dict, self.u_dict = pca_feats.run()
        
        self.X = list()
        tempX = list()
        self.y = list()
        print "\ncombining both user and question data..."
        for idx, entry in self.train_info_dataframe.iterrows():
            tempX.append(csr_matrix(hstack([self.q_dict[entry['q_id']], self.u_dict[entry['u_id']]])))
            self.y.append(entry['answered'])
            
        self.X = csr_matrix(vstack(tempX))
        self.train_xgboost()
        print "\nDone Hot load."

    def compile_pca_train(self):
        print "\nLoading pca data..."
        print "Loading user data..."
        self.u_dict = pickle.load(open("../../data/user_features.pkl",'r'))
        print "Loading user data(complete)"
        print "Loading question data..."
        self.q_dict = pickle.load(open("../../data/question_features.pkl",'r'))
        print "Loading question data(complete)"

        self.X = list()
        tempX = list()
        self.y = list()
        print "\ncombining both user and question data..."
        for idx, entry in self.train_info_dataframe.iterrows():
            tempX.append(csr_matrix(hstack([self.q_dict[entry['q_id']], self.u_dict[entry['u_id']]])))
            self.y.append(entry['answered'])

        self.X = csr_matrix(vstack(tempX))
        self.save_sparse_csr("../../data/csr_mat_train_lsa.dat", self.X)

        print "combining data and save(complete)"
        print "\nLoading pca data(complete)"

    def compile_pca_test(self):
        # Compile train data
        self.compile_pca_train()

        # Compile test data
        self.test_ids_dataframe = pd.read_pickle("../../data/validate_nolabel.pkl")
        self.X_test = list()
        tempX = list()
        print "\tcompiling test info..."
        for idx, entry in self.test_ids_dataframe.iterrows():
            tempX.append(csr_matrix(hstack([self.q_dict[entry['q_id']], self.u_dict[entry['u_id']]])))

        self.X_test = csr_matrix(vstack(tempX))
        self.save_sparse_csr("../../data/csr_mat_test_lsa.dat", self.X_test)

        self.train_xgboost()
        self.predict()

    def fpreproc(self, dtrain, dtest, param):
        label = dtrain.get_label()
        ratio = float(np.sum(label == 0)) / np.sum(label==1)
        param['scale_pos_weight'] = ratio
        return (dtrain, dtest, param)

    def train_xgboost(self):
        # fit model no training data
        #self.model = xgboost.XGBClassifier(max_depth=10, n_estimators=300, learning_rate=0.02, silent=True, objective='binary:logistic', gamma=0.2, min_child_weight=1, max_delta_step=6, subsample=0.8, reg_lambda=3, reg_alpha=1, scale_pos_weight=1).fit(self.X, self.y, eval_metric='auc')

        dtrain = xgboost.DMatrix(self.X, label=self.y)
        self.X = None
        self.y = None
        param = {'max_depth':10, 'n_estimators':300, 'learning_rate':0.02, 'silent':True, 'objective':'binary:logistic', 'gamma':0.2, 'min_child_weight':1, 'max_delta_step':6, 'subsample':0.8, 'reg_lambda':3, 'reg_alpha':1, 'scale_pos_weight':1}
        res = xgboost.cv(param, dtrain, num_boost_round=10, nfold=5, stratified=True, metrics={'auc'}, seed = 0, callbacks=[xgboost.callback.print_evaluation(show_stdv=True)])
#        #fpreproc=self.fpreproc
        print(res)

#        clf = GridSearchCV(
#            self.model,
#            {
#                'max_depth': [3, 6, 10],
#                'n_estimators': [10,50,100],
#                'min_child_weight': [1,3,6]
#            },
#            cv=10,
#            verbose=10
#        )
#        clf.fit(self.X, self.y)
#        best_param, score, _ = max(clf.grid_scores_, key=lambda x:x[1])
#        print 'score:',score
#        for param_name in sorted(best_param.keys()):
#            print("%s: %r" % (param_name, best_param[param_name]))

    def predict(self):
        # make predictions for test data
        y_pred = self.model.predict_proba(self.X_test)
        wfile = open('temp.csv', 'w')
        wfile.write('qid,uid,label\n')
        for i,entry in enumerate(y_pred):
            wfile.write(str(self.test_ids_dataframe['q_id'][i]) +',' + str(self.test_ids_dataframe['u_id'][i]) +','+str(entry[1])+'\n')
        print y_pred.shape

        
#        predictions = [round(value[1]) for value in y_pred]
#       
#       # evaluate predictions
#        accuracy = accuracy_score(self.y_dev, predictions)
#        f1 = f1_score(self.y_dev, predictions, labels=None, pos_label=1)
#        corr = 0
#        for i in range(len(predictions)):
#            if self.y_dev[i] == 1 and self.y_dev[i] == predictions[i]:
#                corr += 1
#        print("Accuracy: %.2f%%, f1: %.2f, correct: %d out of %d" % ((accuracy * 100.0), f1, corr, len(predictions)))

xg = xgboost_wrapper()

if len(sys.argv) > 1:
    if sys.argv[1] == 'load':
        xg.load_data()
    elif sys.argv[1] == 'compile':
        xg.compile_pca_train()
    elif sys.argv[1] == 'test':
        xg.compile_pca_test()
    elif sys.argv[1] == 'grid':
        xg.hot_load()
else:
    xg.load_data()

#xg.train_xgboost()
#xg.predict()
