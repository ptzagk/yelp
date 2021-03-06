import copy
import time

import operator
from gensim import corpora

from topicmodeling.context import lda_context_utils
from utils.constants import Constants

__author__ = 'fpena'


class LdaBasedContext:

    def __init__(self, records):
        self.records = records
        self.target_reviews = None
        self.non_target_reviews = None
        self.num_topics = Constants.TOPIC_MODEL_NUM_TOPICS
        self.topics = range(self.num_topics)
        self.topic_model = None
        self.context_rich_topics = None
        self.topic_weighted_frequency_map = None
        self.topic_ratio_map = None
        self.topic_statistics_map = None
        self.dictionary = None
        self.target_corpus = None
        self.non_target_corpus = None
        self.max_words = None
        self.lda_beta_comparison_operator = None
        if Constants.LDA_BETA_COMPARISON_OPERATOR == 'gt':
            self.lda_beta_comparison_operator = operator.gt
        elif Constants.LDA_BETA_COMPARISON_OPERATOR == 'lt':
            self.lda_beta_comparison_operator = operator.lt
        elif Constants.LDA_BETA_COMPARISON_OPERATOR == 'ge':
            self.lda_beta_comparison_operator = operator.ge
        elif Constants.LDA_BETA_COMPARISON_OPERATOR == 'le':
            self.lda_beta_comparison_operator = operator.le
        elif Constants.LDA_BETA_COMPARISON_OPERATOR == 'eq':
            self.lda_beta_comparison_operator = operator.le
        else:
            raise ValueError('Comparison operator not supported for LDA beta')

    def separate_reviews(self):

        self.target_reviews = []
        self.non_target_reviews = []

        for record in self.records:
            if record[Constants.TOPIC_MODEL_TARGET_FIELD] == \
                    Constants.TOPIC_MODEL_TARGET_REVIEWS:
                self.target_reviews.append(record)
            else:
                self.non_target_reviews.append(record)

        print("num target reviews: %d" % len(self.target_reviews))
        print("num non-target reviews: %d" % len(self.non_target_reviews))

    def generate_review_corpus(self):

        self.separate_reviews()
        self.dictionary = corpora.Dictionary.load(Constants.DICTIONARY_FILE)

        self.target_corpus =\
            [record[Constants.CORPUS_FIELD] for record in self.target_reviews]
        self.non_target_corpus =\
            [record[Constants.CORPUS_FIELD] for record in self.non_target_reviews]

    def build_topic_model(self):
        print('%s: building topic model' %
              time.strftime("%Y/%m/%d-%H:%M:%S"))

        self.topic_model = lda_context_utils.build_topic_model_from_corpus(
            self.target_corpus, self.dictionary)
        print('%s: topic model built' %
              time.strftime("%Y/%m/%d-%H:%M:%S"))

    def update_reviews_with_topics(self):
        lda_context_utils.update_reviews_with_topics(
            self.topic_model, self.target_corpus, self.target_reviews)
        lda_context_utils.update_reviews_with_topics(
            self.topic_model, self.non_target_corpus, self.non_target_reviews)

        print('%s: updated reviews with topics' %
              time.strftime("%Y/%m/%d-%H:%M:%S"))

    def get_context_rich_topics(self):
        """
        Returns a list with the topics that are context rich and their
        specific/generic frequency ratio

        :rtype: list[(int, float)]
        :return: a list of pairs where the first position of the pair indicates
        the topic and the second position indicates the specific/generic
        frequency ratio
        """
        if Constants.TOPIC_WEIGHTING_METHOD == Constants.ALL_TOPICS:
            self.topic_ratio_map = {}
            self.topic_weighted_frequency_map = {}

            for topic in range(self.num_topics):
                self.topic_ratio_map[topic] = 1
                self.topic_weighted_frequency_map[topic] = 1

            # export_all_topics(self.topic_model)
            # print('%s: exported topics' % time.strftime("%Y/%m/%d-%H:%M:%S"))

            sorted_topics = sorted(
                self.topic_ratio_map.items(), key=operator.itemgetter(1),
                reverse=True)

            self.context_rich_topics = sorted_topics
            print('all_topics')
            print('context topics: %d' % len(self.context_rich_topics))
            return sorted_topics

        # numpy.random.seed(0)
        topic_ratio_map = {}
        self.topic_weighted_frequency_map = {}
        lower_than_alpha_count = 0.0
        lower_than_beta_count = 0.0
        non_contextual_topics = set()
        for topic in range(self.num_topics):
            # print('topic: %d' % topic)
            weighted_frq = lda_context_utils.calculate_topic_weighted_frequency(
                topic, self.records)
            target_weighted_frq = \
                lda_context_utils.calculate_topic_weighted_frequency(
                    topic, self.target_reviews)
            non_target_weighted_frq = \
                lda_context_utils.calculate_topic_weighted_frequency(
                    topic, self.non_target_reviews)

            if weighted_frq < Constants.CONTEXT_EXTRACTOR_ALPHA:
                non_contextual_topics.add(topic)
                # print('non-contextual_topic: %d' % topic)
                lower_than_alpha_count += 1.0

            if non_target_weighted_frq == 0:
                # We can't know if the topic is good or not
                non_contextual_topics.add(topic)
                ratio = 'N/A'
                # non_contextual_topics.add(topic)
            else:
                ratio = target_weighted_frq / non_target_weighted_frq

            # print('topic: %d --> ratio: %f\tspecific: %f\tgeneric: %f' %
            #       (topic, ratio, target_weighted_frq, non_target_weighted_frq))

            if self.lda_beta_comparison_operator(
                    ratio, Constants.CONTEXT_EXTRACTOR_BETA):
                non_contextual_topics.add(topic)
                lower_than_beta_count += 1.0
                # print('non-contextual_topic: %d' % topic)

            topic_ratio_map[topic] = ratio
            self.topic_weighted_frequency_map[topic] = weighted_frq

        self.topic_ratio_map = copy.deepcopy(topic_ratio_map)

        # lda_context_utils.export_topics(self.topic_model, topic_ratio_map)
        # print('%s: exported topics' % time.strftime("%Y/%m/%d-%H:%M:%S"))

        for topic in non_contextual_topics:
            topic_ratio_map.pop(topic)

        # print('non contextual topics', len(non_contextual_topics))
        # for topic in topic_ratio_map.keys():
        #     print(topic, topic_ratio_map[topic])
        #
        sorted_topics = sorted(
            topic_ratio_map.items(), key=operator.itemgetter(1), reverse=True)

        # for topic in sorted_topics:
        #     topic_index = topic[0]
        #     ratio = topic[1]
        #     print('topic', ratio, topic_index, self.topic_model.print_topic(topic_index, topn=50))

        # print('num_topics', len(self.topics))
        print('context topics: %d' % len(topic_ratio_map))
        print('topics lower than alpha: %d' % lower_than_alpha_count)
        print('topics lower than beta: %d' % lower_than_beta_count)
        self.context_rich_topics = sorted_topics
        print(self.context_rich_topics)
        self.max_words = []
        for topic in self.context_rich_topics:
            self.max_words.append(
                self.topic_model.show_topic(topic[0], 1)[0][1])

        return sorted_topics

    def find_contextual_topics(self, records, text_sampling_proportion=None):
        for record in records:
            # numpy.random.seed(0)
            topic_distribution = lda_context_utils.get_topic_distribution(
                record, self.topic_model, self.dictionary,
                Constants.CONTEXT_EXTRACTOR_EPSILON, text_sampling_proportion,
                self.max_words
            )

            # We calculate the sum of the probabilities of the contextual topics
            # to then normalize the contextual vector
            context_topics_sum = 0.0
            for i in self.context_rich_topics:
                context_topics_sum += topic_distribution[i[0]]

            topics_map = {}
            for i in self.context_rich_topics:
                topic_id = 'topic' + str(i[0])
                if context_topics_sum > 0:
                    topics_map[topic_id] =\
                        topic_distribution[i[0]] / 1.0
                else:
                    topics_map[topic_id] = 0.0

            topics_map['nocontexttopics'] = 1 - context_topics_sum

            record[Constants.CONTEXT_TOPICS_FIELD] = topics_map

        # print(self.context_rich_topics)
        # print('total_topics', len(self.context_rich_topics))

        return records

    def print_topic_model(self, num_terms=10):

        return [
            self.topic_model.print_topic(topic_id, num_terms)
            for topic_id in range(self.num_topics)
            ]

    def clear_reviews(self):
        self.records = None
        self.target_reviews = None
        self.non_target_reviews = None
        self.target_corpus = None
        self.non_target_corpus = None


def main():
    pass

# numpy.random.seed(0)
#
# start = time.time()
# main()
# end = time.time()
# total_time = end - start
# print("Total time = %f seconds" % total_time)
