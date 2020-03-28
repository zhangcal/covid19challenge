'''
Polling places

Calvin Zhang and Xuechen Hong

Main file for polling place simulation
'''

import sys
import random
import queue
import util


class Patient(object):
    def __init__(self, arrival_time, voting_duration):
        '''
        Constructor for the Voter class

        Input:
            arrival_time: (float) Time in minutes at which the voter arrives
            voting_duration: (float) Time in minutes the voter stays
            in the voting booth
        '''

        self.arrival_time = arrival_time
        self.voting_duration = voting_duration

        # start_time and departure_time will be calculated later
        self.start_time = None
        self.departure_time = None


class Hospital(object):
    def __init__(self, name, hours_open, max_num_voters,
                 arrival_rate, voting_duration_rate):
        '''
        Constructor for the Precinct class

        Input:
            name: (str) Name of the precinct
            hours_open: (int) Hours the precinct will remain open
            max_num_voters: (int) number of voters in the precinct
            arrival_rate: (float) rate at which voters arrive
            voting_duration_rate: (float) lambda for voting duration
        '''

        self.name = name
        self.hours_open = hours_open
        self.max_num_voters = max_num_voters
        self.arrival_rate = arrival_rate
        self.voting_duration_rate = voting_duration_rate


    def next_voter(self, prev_voter):
        '''
        Generate the next voter as Voter object given the previous voter

        Inputs:
            prev_voter: the previous Voter object with arrival_time and
                        voting_duration attributes

        Return:
            next_voter: Voter object of next voter with new arrival_time
                        and voting_duration atrributes
        '''

        # Extract gap between arrival times and new voting duration
        # from poisson
        gap, voting_duration = util.gen_poisson_voter_parameters(\
        self.arrival_rate, self.voting_duration_rate)
        new_arrival_time = prev_voter.arrival_time + gap
        next_voter = Patient(new_arrival_time, voting_duration)

        return next_voter


    def simulate(self, seed, num_booths):
        '''
        Simulate a day of voting

        Input:
            seed: (int) Random seed to use in the simulation
            num_booths: (int) Number of booths to use in the simulation

        Return:
            List of voters who voted in the precinct
        '''
        
        random.seed(seed)

        # Initialize return list
        voter_list = []

        # Initialize default base voter (not the first voter!)
        # as reference voter in self.next_voter
        base_voter = Patient(0, 0)

        # Create a single queue of VotingBooths class to hold
        # departure times of all people currently IN voting booths
        # Max queue size should be capped at num_booths
        all_booths = Bed(queue.PriorityQueue(num_booths))

        for i in range(self.max_num_voters):
            new_voter = self.next_voter(base_voter)

            # When booths aren't full
            if not all_booths.check_full(): 
                new_voter.start_time = new_voter.arrival_time
                new_voter.departure_time = new_voter.start_time + \
                new_voter.voting_duration
                all_booths.add_voter_dep(new_voter.departure_time)
            
            # When booths are full
            else:
                # min_departure_time is the earliest departure time among
                # all people currently in all_booths
                min_departure_time = all_booths.get_remove_voter_dep()

                # Takes care of people arriving after or before 
                # a booth opens up
                if new_voter.arrival_time > min_departure_time:
                    new_voter.start_time = new_voter.arrival_time
                else:
                    new_voter.start_time = min_departure_time

                new_voter.departure_time = new_voter.start_time + \
                new_voter.voting_duration
                all_booths.add_voter_dep(new_voter.departure_time)

            # Ignores people arriving after booth closed
            if new_voter.arrival_time <= self.hours_open * 60:
                voter_list.append(new_voter)

            # Update base_voter for use in self.next_voter to
            # generate new_voter
            base_voter = new_voter

        return voter_list
        

class Bed(object):
    def __init__(self, bed_queue):
        '''
        Constructor for the VotingBooths class

        Inputs:
            booth_queue: PriorityQueue object to model peoples' departure
            times in booths. This is set to private attribute.
        '''

        self._bed_queue = bed_queue


    def add_voter_dep(self, voter_dep):
        '''
        Adds voters' departure time in minutes to _booth_queue attribute
        of VotingBooths object

        Inputs:
            voter_dep: (float) Departure time of a voter in minutes

        Return:
            Doesn't return anything new. Just modifies _booth_queue. 
        '''

        self._bed_queue.put(voter_dep, block=False)


    def get_remove_voter_dep(self):
        '''
        Extracts and removes earliest (minimum) voter departure time
        from the _booth_queue attribute.

        Inputs:
            Nothing. Modifies VotingBooths object itself. 

        Return:
            Minimum voter departure time (float) from _booth_queue. 
        '''

        return self._bed_queue.get(block=False)


    def check_full(self):
        '''
        Checks whether the _booth_queue is full

        Inputs:
            Nothing. Checks VotingBooths object itself. 

        Return:
            Boolean value for whether _booth_queue is full
        '''
        return self._bed_queue.full()


def find_avg_wait_time(hospital, num_beds, ntrials, initial_seed=0):
    '''
    Simulates a precinct multiple times with a given number of booths
    For each simulation, computes the average waiting time of the voters,
    and returns the median of those average waiting times.

    Input:
        precinct: (dictionary) A precinct dictionary
        num_booths: (int) The number of booths to simulate the precinct with
        ntrials: (int) The number of trials to run
        initial_seed: (int) initial seed for random number generator

    Output:
        The median of the average waiting times returned by simulating
        the precinct 'ntrials' times.
    '''

    # Use information in precinct dictionary to construct Precinct
    # object
    hospital_object = Hospital(hospital["name"], hospital["hours_open"],
                               hospital["num_voters"], hospital["voter_distribution"]["arrival_rate"],
                               hospital["voter_distribution"]["voting_duration_rate"])

    # Accumulate list of trial averages.
    trial_averages = []
    for trial in range(ntrials):
        patient_list = hospital_object.simulate(initial_seed, num_beds)
        average_one_trial = sum([v.start_time - \
        v.arrival_time for v in patient_list]) / len(patient_list)
        trial_averages.append(average_one_trial)

        # Increments seed in random.seed() used in simulate method
        # of Precinct class
        initial_seed += 1

    trial_averages = sorted(trial_averages)

    return trial_averages[ntrials // 2] # Median trial average


def find_number_of_booths(hospital, target_wait_time, max_num_beds,
                          ntrials, seed=0):
    '''
    Finds the number of booths a precinct needs to guarantee a bounded
    (average) waiting time.

    Input:
        precinct: (dictionary) A precinct dictionary
        target_wait_time: (float) The desired (maximum) waiting time
        max_num_booths: (int) The maximum number of booths this
                        precinct can support
        ntrials: (int) The number of trials to run when computing
                 the average waiting time
        seed: (int) A random seed

    Output:
        A tuple (num_booths, waiting_time) where:
        - num_booths: (int) The smallest number of booths that ensures
                      the average waiting time is below target_waiting_time
        - waiting_time: (float) The actual average waiting time with that
                        number of booths

        If the target waiting time is infeasible, returns (0, None)
    '''

    for num_beds in range(1, max_num_beds + 1):
        avg_wait_time = find_avg_wait_time(hospital, num_beds, ntrials,
                                           seed)
        if avg_wait_time < target_wait_time:

            return (num_beds, avg_wait_time)
        
    return (0, None)

