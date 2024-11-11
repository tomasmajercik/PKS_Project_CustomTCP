import time

def calc_print_len(string):
    return len(string)
def print_receive(count):
    for _ in count:
        print("<", end='')
    print()
def print_send(count):
    for _ in count:
        print(">", end='')
    print()

class Prints:


    @staticmethod
    def menu():
        time.sleep(0.1)
        print("\nMENU:")
        # print("'m' for message | 'f' for file | 'sml' for simulate message lost | '!quit' for quit")
        print("'m' for message | 'f' for file | 'cfl' for info or change fragmentation size | '!q / !quit' for quit")
        choice = input("Choose an option: ").strip()
        return choice

    @staticmethod
    def info_menu():
        print("MENU:")
        # print("'m' for message | 'f' for file | 'sml' for simulate message lost | '!quit' for quit")
        print("'m' for message | 'f' for file | 'cfl' for info or change fragmentation size | '!q / !quit' for quit")

    @staticmethod
    def start_termination():
        print(f"\n\n #Another peer terminates the connection!")
        print(f"1. RECEIVED termination TER")

    @staticmethod
    def checksum_err():
        print("! Checksum does not match !")

    @staticmethod
    def out_of_order_err():
        print("!!Out of order packet received, ignoring!!")

    @staticmethod
    def received_fragmented_package(packet, last=False):
        output_to_string = (f"Received fragment: {packet.seq_num}|{packet.ack_num}|{packet.identification}|"
                            f"{packet.checksum}|{packet.flags}|{packet.message}")
        print(f"\n\n<")

        if not last:
            print_receive(output_to_string)
            print(output_to_string)
            print_receive(output_to_string)
        if last:
            print_receive(output_to_string + "    ")
            print(
                f"Received last fragment: {packet.seq_num}|{packet.ack_num}|{packet.identification}|{packet.checksum}|{packet.flags}|{packet.message}")
            print_receive(output_to_string + "    ")

        print("\n")

    @staticmethod
    def received_joined_fragments(data, num):
        output_to_string = f"Received: {data} (message was received as {num} fragments)"

        print(f"\n\n")
        print_receive(output_to_string)
        print(output_to_string)
        print_receive(output_to_string)
        print("\n")

    @staticmethod
    def received_package(packet):
        output_to_string = f"Received: {packet.seq_num}|{packet.ack_num}|{packet.checksum}|{packet.flags}|{packet.message}"
        print(f"\n\n")
        print_receive(output_to_string)
        print(output_to_string)
        print_receive(output_to_string)
        print(f"\n")

    @staticmethod
    def send_packet(packet):
        output_to_string = f"Sent: {packet.seq_num}|{packet.ack_num}|{packet.checksum}|{packet.flags}|{packet.message}"
        print("\n")
        print_send(output_to_string)
        print(output_to_string)
        # return output_to_string

    @staticmethod
    def print_receive_file():
        print("Starting receiving data, please wait...")
        print("----------------------------------------")