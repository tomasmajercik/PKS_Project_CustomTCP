import queue
import socket
import random
import threading

from collections import deque

from Packet import Packet
from Functions import Functions
from Flags import Flags

FRAGMENT_SIZE = 5
MAX_FRAGMENT_SIZE = 1457 # Ethernet-IP Header-UDP Header-Custom Protocol Header = 1500−20−8-15 = 1457

class Peer:
    def __init__(self, my_ip, target_ip, listen_port, send_port):
        #queue
        self.data_queue = deque()
        self.command_queue = queue.Queue()
        # routing variables
        self.id = (my_ip, listen_port)
        self.peer_address = (target_ip, send_port)
        # syn/ack variables
        self.seq_num = random.randint(0, 1000)
        self.ack_num = 0
        # sockets
        self.receiving_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receiving_socket.bind(self.id)
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # threading variables
        self.queue_lock = threading.Lock()
        self.received_ack = threading.Event()

#### HANDSHAKE #########################################################################################################
    def handshake(self):
        max_retries = 15
        retries = 0

        # Set timeout for waiting on incoming packets
        self.receiving_socket.settimeout(2.0)

        while retries < max_retries:
            try:
                try:
                    data, addr = self.receiving_socket.recvfrom(1500)
                    received_packet = Packet.deconcatenate(data)

                    if received_packet.flags == Flags.SYN:  # Received SYN from the other peer
                        print(f"\n< Received handshake SYN <")
                        self.ack_num = received_packet.seq_num + 1
                        SYN_ACK_packet = Packet(seq_num=self.seq_num, ack_num=self.ack_num, flags=Flags.SYN_ACK)
                        self.send_socket.sendto(SYN_ACK_packet.concatenate(), self.peer_address)
                        print(f"> Sent handshake SYN/ACK >")
                        self.seq_num += 1

                    elif received_packet.flags == Flags.SYN_ACK:  # Received SYN/ACK in response to our SYN
                        print(f"< Received handshake SYN/ACK <")
                        self.seq_num += 1
                        ACK_packet = Packet(seq_num=self.seq_num, ack_num=self.ack_num, flags=Flags.ACK)
                        self.send_socket.sendto(ACK_packet.concatenate(), self.peer_address)
                        self.ack_num = received_packet.seq_num + 1
                        print(f"> Sent handshake ACK >")
                        print(
                            f"\n## Handshake successful, connection initialized seq: {self.seq_num} ack:{self.ack_num}")
                        return True

                    elif received_packet.flags == Flags.ACK:  # Received final ACK confirming the handshake
                        print(f"< Received handshake ACK <")
                        print(
                            f"\n## Handshake successful, connection initialized seq: {self.seq_num} ack:{self.ack_num}")
                        return True

                except socket.timeout:
                    # If nothing was received, initiate the handshake by sending SYN
                    if retries == 0:
                        SYN_packet = Packet(seq_num=self.seq_num, ack_num=self.ack_num, flags=Flags.SYN)
                        self.send_socket.sendto(SYN_packet.concatenate(), self.peer_address)
                        print(f"\n> Sent handshake SYN (attempt {retries + 1}) >")

                retries += 1

            except socket.timeout:
                print(f"Retrying... (attempt {retries + 1})")

        print(f"Handshake timeout after {max_retries} retries")
        self.receiving_socket.close()
        return False

    #### ENQUEING ##########################################################################################################
    def enqueue_message(self, message="", flags_to_send=Flags.NONE, push_to_front=False):
        if len(message) < FRAGMENT_SIZE:
            packet = Packet(identification=0, checksum=Functions.calc_checksum(message), flags=flags_to_send,
                            data=message)
            if push_to_front:
                with self.queue_lock:
                    self.data_queue.appendleft(packet)
            elif not push_to_front:
                with self.queue_lock:
                    self.data_queue.append(packet)

        elif len(message) >= FRAGMENT_SIZE:  # split data to be sent into multiple fragments if needed
            fragments = [message[i:i + FRAGMENT_SIZE] for i in range(0, len(message), FRAGMENT_SIZE)]
            for i, fragment in enumerate(fragments):
                if i == len(fragments) - 1:  # if it is last fragment, mark it with FRP/ACK
                    fragment_flag = Flags.FRP_ACK
                else:
                    fragment_flag = Flags.FRP

                packet = Packet(seq_num=self.seq_num, ack_num=self.ack_num, identification=i,
                                checksum=Functions.calc_checksum(fragment.encode()), flags=fragment_flag,
                                data=fragment)
                with self.queue_lock:
                    self.data_queue.append(packet)
        return
#### SENDING AND RECEIVING #############################################################################################
    def send_data_from_queue(self): # is in send_thread thread
        while True:
            if not self.data_queue: # if queue is empty, do nothing
                continue

            ######## prepare the package #######################
            packet_to_send = self.data_queue[0] # take first from queue
            packet_to_send.seq_num = self.seq_num # set current seq
            packet_to_send.ack_num = self.ack_num # set current ack

            ####### STOP & WAIT ########################################################################################
            while True:
                self.received_ack.clear()

                ######## send the packet ##########################
                self.send_socket.sendto(packet_to_send.concatenate(), self.peer_address)

                #### flags that don't have to be acknowledged ###
                if packet_to_send.flags in {Flags.ACK}:
                    with self.queue_lock: self.data_queue.popleft()
                    break

                # Wait for ACK or timeout
                ack_received = self.received_ack.wait(timeout=5.0)

                if ack_received:
                    # print("Ack received")
                    self.seq_num += len(packet_to_send.data)
                    with self.queue_lock: self.data_queue.popleft()
                    break
                else:
                    print("\n!ACK not received, resending packet! \n")




        return
    def receive_data(self): # is NOT in thread so the program can terminate later
        fragments = [] # array to store received fragments
        while True:
            try:
                # set timeout for waiting
                self.receiving_socket.settimeout(2.0)

                # receive data
                packet_data, addr = self.receiving_socket.recvfrom(1500)
                rec_packet = Packet.deconcatenate(packet_data)

                ##### rec. ACK #########################################################################################
                if rec_packet.flags == Flags.ACK: # and rec_packet.ack_num == self.seq_num + 1: - if want to check seq/ack
                    self.received_ack.set() # this stays only in this if
                    self.ack_num = rec_packet.seq_num + 1
                    print("ack received")
                    continue
                ##### FRagmented Packet ################################################################################
                if rec_packet.flags == Flags.FRP:
                    fragments.append(rec_packet)
                    self.enqueue_message("ack", flags_to_send=Flags.ACK, push_to_front=True) # send ack
                    self.ack_num += rec_packet.seq_num + 1
                    continue
                if rec_packet.flags == Flags.FRP_ACK: # last fragmented package
                    fragments.append(rec_packet)
                    self.enqueue_message("ack", flags_to_send=Flags.ACK, push_to_front=True) # send ack
                    self.ack_num += rec_packet.seq_num + 1
                    message, number_of_fragments = Functions.rebuild_fragmented_message(fragments)
                    print(f"\n<<<<<<\nRECEIVED: {message.decode()} (message was received as {number_of_fragments} fragments)\n<<<<<< \n")
                    fragments = [] # reset fragments
                    continue
                ####### Change Fragment Limit ##########################################################################
                if rec_packet.flags == Flags.CFL:
                    global FRAGMENT_SIZE
                    old_limit = FRAGMENT_SIZE
                    self.enqueue_message("ack", flags_to_send=Flags.ACK, push_to_front=True) # send ack
                    FRAGMENT_SIZE = int(rec_packet.data.decode())
                    print("\n\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                    print(f"Other peer has just changed fragmentation limit from {old_limit} to {FRAGMENT_SIZE}")
                    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
                ####### Ordinary messages ##############################################################################
                if rec_packet.flags == Flags.NONE: # is an ordinary messaga
                    if rec_packet.checksum != Functions.calc_checksum(rec_packet.data): # calculate checksum
                        print("checksum does not match - message corrupted")
                        continue

                    print(f"\n\n<<<<<<\nRECEIVED data: {rec_packet.data.decode()} \n<<<<<< \n")
                    #### send ACK to signal data were received correctly
                    self.ack_num = rec_packet.seq_num + len(rec_packet.data)
                    self.enqueue_message("ack", flags_to_send=Flags.ACK, push_to_front=True) # send ack
                    continue
                ########################################################################################################


            except socket.timeout:
                continue

#### PROGRAM CONTROL ###################################################################################################
    def input_handler(self):
        Functions.info_menu()  # show menu
        while True:
            command = input("")
            self.command_queue.put(command)

    def manage_user_input(self): # is in input_thread thread
        while True:
            if self.command_queue.empty():
                continue
            choice = self.command_queue.get()

            if choice == "m": #message
                print("\n##############")
                message = self.command_queue.get()
                print("##############\n")
                self.enqueue_message(message)
                continue
            if choice == "cfl": # change fragment limit
                global FRAGMENT_SIZE
                print("\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                print(f"Fragment size is currently set to {FRAGMENT_SIZE}")

                print("Enter 'q' for quit   or    enter new fragment limit (or 'MAX' to set max fragments possible): ")
                new_limit = self.command_queue.get()
                if new_limit == 'q':
                    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
                    continue
                else:
                    if new_limit == 'MAX':
                        new_limit = str(MAX_FRAGMENT_SIZE)
                    try:
                        new_limit = int(new_limit)  # Try converting input to an integer
                        if new_limit > MAX_FRAGMENT_SIZE:
                            print(f"Cannot change fragmentation limit above {MAX_FRAGMENT_SIZE}.")
                            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
                            continue
                        else:
                            print(f"Changed fragmentation limit from {FRAGMENT_SIZE} to {new_limit}")
                            FRAGMENT_SIZE = int(new_limit)
                            self.enqueue_message(str(FRAGMENT_SIZE), Flags.CFL, True)
                            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
                    except ValueError:
                        print("Invalid input. Please enter a number, 'MAX', or 'q' to quit.")
                        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
                        continue
            else:
                print("invalid command")



if __name__ == '__main__':

    # MY_IP = input("Enter YOUR IP address: ")
    # PEERS_IP = input("Enter PEER's IP address: ")
    # PEER_SEND_PORT = int(input("Enter your send port (should be the same as second's peer listening port): "))
    # PEER_LISTEN_PORT = int(input("Enter your listening port (should be the same as second's peer sending port): "))
    #
    # if MY_IP < PEERS_IP: start_handshake = True
    # elif MY_IP==PEERS_IP:
    #     if PEER_LISTEN_PORT > PEER_SEND_PORT:
    #         start_handshake = True
    #     else:
    #         start_handshake = False
    # else: start_handshake = False

    MY_IP = "localhost"
    whos_this = input("peer one (1) or peer two (2): ")
    if whos_this == "1":
        PEERS_IP = "localhost"
        PEER_LISTEN_PORT = 8000
        PEER_SEND_PORT = 7000
    else:
        PEERS_IP = "localhost"
        PEER_LISTEN_PORT = 7000
        PEER_SEND_PORT = 8000

    peer = Peer(MY_IP, PEERS_IP, PEER_LISTEN_PORT, PEER_SEND_PORT)
#### HANDSHAKE #########################################################################################################
    if not peer.handshake():
        print("Failed to establish connection exiting.")
        exit()
    else:
        print(f"#  Starting data exchange\n")

#### THREADS ###########################################################################################################
    input_manage_thread = threading.Thread(target=peer.input_handler)
    input_manage_thread.daemon = True
    input_manage_thread.start()

    input_thread = threading.Thread(target=peer.manage_user_input)
    input_thread.daemon = True
    input_thread.start()

    send_thread = threading.Thread(target=peer.send_data_from_queue)
    send_thread.daemon = True
    send_thread.start()

    peer.receive_data()















