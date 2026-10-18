
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX 100
#define LANES 4

struct Vehicle {
    int id;
    int type;
};

struct Queue {
    struct Vehicle vehicles[MAX];
    int front;
    int rear;
    int count;
};

struct Queue lanes[LANES];

const char *laneNames[LANES] = {
    "North", "South", "East", "West"
};

const char *vehicleTypes[] = {
    "", "Car", "Bus", "Bike"
};

int passed[LANES] = {0};
int lastServed = -1;

void initializeQueue(struct Queue *q) {
    q->front = 0;
    q->rear = -1;
    q->count = 0;
}

int vehicleExists(int id) {
    for (int i = 0; i < LANES; i++) {
        for (int j = 0; j < lanes[i].count; j++) {
            int index = (lanes[i].front + j) % MAX;
            if (lanes[i].vehicles[index].id == id)
                return 1;
        }
    }
    return 0;
}

int enqueue(struct Queue *q, int id, int type) {
    if (q->count >= MAX)
        return 0;

    q->rear = (q->rear + 1) % MAX;
    q->vehicles[q->rear].id = id;
    q->vehicles[q->rear].type = type;
    q->count++;
    return 1;
}

int dequeueLane(int lane, int *id, int *type) {
    struct Queue *q = &lanes[lane];

    if (q->count == 0)
        return 0;

    *id = q->vehicles[q->front].id;
    *type = q->vehicles[q->front].type;

    q->front = (q->front + 1) % MAX;
    q->count--;
    passed[lane]++;
    return 1;
}

void printStatus(void) {
    printf("{\"lanes\":[");

    for (int i = 0; i < LANES; i++) {
        if (i > 0)
            printf(",");

        printf("{\"name\":\"%s\",\"waiting\":%d,\"passed\":%d,\"vehicles\":[",
               laneNames[i], lanes[i].count, passed[i]);

        for (int j = 0; j < lanes[i].count; j++) {
            int index = (lanes[i].front + j) % MAX;

            if (j > 0)
                printf(",");

            printf("{\"id\":%d,\"type\":\"%s\"}",
                   lanes[i].vehicles[index].id,
                   vehicleTypes[lanes[i].vehicles[index].type]);
        }

        printf("]}");
    }

    printf("],\"lastServed\":%d}\n", lastServed);
    fflush(stdout);
}

void printResult(int ok, const char *message, int selected,
                 int vehicleId, int vehicleType, int vehicleLane) {
    printf("{\"ok\":%s,\"message\":\"%s\",\"selectedLane\":",
           ok ? "true" : "false", message);

    if (selected >= 0 && selected < LANES)
        printf("\"%s\"", laneNames[selected]);
    else
        printf("null");

    printf(",\"vehicle\":");

    if (vehicleId > 0 && vehicleType >= 1 && vehicleType <= 3) {
        printf("{\"id\":%d,\"type\":\"%s\",\"lane\":\"%s\"}",
               vehicleId, vehicleTypes[vehicleType],
               laneNames[vehicleLane]);
    } else {
        printf("null");
    }

    printf("}\n");
    fflush(stdout);
}

void processCommand(char *line) {
    char command[20] = "";
    int a = 0, b = 0, c = 0;

    if (sscanf(line, "%19s", command) != 1) {
        printResult(0, "Empty command", -1, 0, 0, 0);
        return;
    }

    if (strcmp(command, "STATUS") == 0) {
        printStatus();
        return;
    }

    if (strcmp(command, "ADD") == 0) {
        if (sscanf(line, "%19s %d %d %d",
                   command, &a, &b, &c) != 4 ||
            a < 1 || a > LANES || b <= 0 || c < 1 || c > 3) {
            printResult(0, "Invalid vehicle details", -1, 0, 0, 0);
            return;
        }

        if (vehicleExists(b)) {
            printResult(0, "Vehicle ID already exists", -1, 0, 0, 0);
            return;
        }

        if (!enqueue(&lanes[a - 1], b, c)) {
            printResult(0, "Lane is full", -1, 0, 0, 0);
            return;
        }

        printResult(1, "Vehicle added successfully", -1, 0, 0, 0);
        return;
    }

    if (strcmp(command, "SIGNAL") == 0) {
        int id, type;

        if (sscanf(line, "%19s %d", command, &a) != 2 ||
            a < 1 || a > LANES) {
            printResult(0, "Invalid lane", -1, 0, 0, 0);
            return;
        }

        if (!dequeueLane(a - 1, &id, &type)) {
            printResult(0, "No vehicles waiting in this lane",
                        a - 1, 0, 0, 0);
            return;
        }

        lastServed = a - 1;
        printResult(1, "Manual signal activated", a - 1,
                    id, type, a - 1);
        return;
    }

    if (strcmp(command, "AUTO") == 0) {
        int maximum = 0;
        int selected = -1;
        int id, type;

        for (int i = 0; i < LANES; i++) {
            if (lanes[i].count > maximum)
                maximum = lanes[i].count;
        }

        if (maximum == 0) {
            printResult(0, "No vehicles waiting", -1, 0, 0, 0);
            return;
        }

        for (int step = 1; step <= LANES; step++) {
            int i = (lastServed + step + LANES) % LANES;

            if (lanes[i].count == maximum) {
                selected = i;
                break;
            }
        }

        dequeueLane(selected, &id, &type);
        lastServed = selected;

        printResult(1, "Automatic signal activated", selected,
                    id, type, selected);
        return;
    }

    if (strcmp(command, "SEARCH") == 0) {
        if (sscanf(line, "%19s %d", command, &a) != 2 || a <= 0) {
            printResult(0, "Invalid vehicle ID", -1, 0, 0, 0);
            return;
        }

        for (int i = 0; i < LANES; i++) {
            for (int j = 0; j < lanes[i].count; j++) {
                int index = (lanes[i].front + j) % MAX;

                if (lanes[i].vehicles[index].id == a) {
                    printResult(1, "Vehicle found", -1, a,
                                lanes[i].vehicles[index].type, i);
                    return;
                }
            }
        }

        printResult(0, "Vehicle not found in waiting queues",
                    -1, 0, 0, 0);
        return;
    }

    printResult(0, "Unknown command", -1, 0, 0, 0);
}

void displayQueues(void) {
    printf("\n========== TRAFFIC QUEUES ==========\n");

    for (int i = 0; i < LANES; i++) {
        printf("\n%s Lane (%d vehicles):\n",
               laneNames[i], lanes[i].count);

        if (lanes[i].count == 0) {
            printf("No vehicles waiting.\n");
            continue;
        }

        for (int j = 0; j < lanes[i].count; j++) {
            int index = (lanes[i].front + j) % MAX;

            printf("ID: %d | Type: %s\n",
                   lanes[i].vehicles[index].id,
                   vehicleTypes[lanes[i].vehicles[index].type]);
        }
    }
}

void showSignal(int selected) {
    int id, type;

    printf("\n%s Lane: GREEN\n", laneNames[selected]);

    for (int i = 0; i < LANES; i++) {
        if (i != selected)
            printf("%s Lane: RED\n", laneNames[i]);
    }

    if (dequeueLane(selected, &id, &type))
        printf("Vehicle %d (%s) passed through the green signal.\n",
               id, vehicleTypes[type]);
    else
        printf("No vehicles waiting in this lane!\n");

    lastServed = selected;
}

void addVehicle(void) {
    int lane, id, type;

    printf("\nSelect lane:\n");
    for (int i = 0; i < LANES; i++)
        printf("%d. %s\n", i + 1, laneNames[i]);

    printf("Enter lane number: ");
    if (scanf("%d", &lane) != 1)
        return;

    printf("Enter vehicle ID: ");
    if (scanf("%d", &id) != 1)
        return;

    printf("Enter vehicle type (1=Car, 2=Bus, 3=Bike): ");
    if (scanf("%d", &type) != 1)
        return;

    if (lane < 1 || lane > LANES || id <= 0 ||
        type < 1 || type > 3) {
        printf("Invalid vehicle details!\n");
        return;
    }

    if (vehicleExists(id)) {
        printf("This vehicle ID already exists!\n");
        return;
    }

    if (enqueue(&lanes[lane - 1], id, type))
        printf("Vehicle %d added successfully!\n", id);
    else
        printf("Lane is full!\n");
}

void controlSignal(void) {
    int lane;

    printf("\nSelect lane for GREEN signal:\n");
    for (int i = 0; i < LANES; i++)
        printf("%d. %s\n", i + 1, laneNames[i]);

    printf("Enter lane number: ");
    if (scanf("%d", &lane) != 1)
        return;

    if (lane < 1 || lane > LANES) {
        printf("Invalid lane number!\n");
        return;
    }

    showSignal(lane - 1);
}

void automaticSignal(void) {
    int maximum = 0;
    int selected = -1;

    for (int i = 0; i < LANES; i++) {
        if (lanes[i].count > maximum)
            maximum = lanes[i].count;
    }

    if (maximum == 0) {
        printf("\nNo vehicles waiting in any lane.\n");
        return;
    }

    for (int step = 1; step <= LANES; step++) {
        int i = (lastServed + step + LANES) % LANES;

        if (lanes[i].count == maximum) {
            selected = i;
            break;
        }
    }

    printf("\nAutomatic signal selected: %s Lane\n",
           laneNames[selected]);
    showSignal(selected);
}

void searchVehicle(void) {
    int id, found = 0;

    printf("\nEnter vehicle ID to search: ");
    if (scanf("%d", &id) != 1)
        return;

    for (int i = 0; i < LANES; i++) {
        for (int j = 0; j < lanes[i].count; j++) {
            int index = (lanes[i].front + j) % MAX;

            if (lanes[i].vehicles[index].id == id) {
                printf("\nVehicle found!\n");
                printf("Vehicle ID: %d\n", id);
                printf("Vehicle Type: %s\n",
                       vehicleTypes[lanes[i].vehicles[index].type]);
                printf("Current Lane: %s\n", laneNames[i]);
                printf("Status: Waiting\n");
                found = 1;
                break;
            }
        }

        if (found)
            break;
    }

    if (!found)
        printf("Vehicle not found in the waiting queues.\n");
}

void displayStatistics(void) {
    int totalWaiting = 0;
    int totalPassed = 0;

    printf("\n========== TRAFFIC STATISTICS ==========\n");

    for (int i = 0; i < LANES; i++) {
        printf("%s Lane: Waiting = %d, Passed = %d\n",
               laneNames[i], lanes[i].count, passed[i]);
        totalWaiting += lanes[i].count;
        totalPassed += passed[i];
    }

    printf("\nTotal vehicles waiting: %d\n", totalWaiting);
    printf("Total vehicles passed: %d\n", totalPassed);
}

int main(int argc, char *argv[]) {
    for (int i = 0; i < LANES; i++)
        initializeQueue(&lanes[i]);

    if (argc > 1 && strcmp(argv[1], "server") == 0) {
        char line[256];

        while (fgets(line, sizeof(line), stdin) != NULL)
            processCommand(line);

        return 0;
    }

    int choice;

    do {
        printf("\n===== TRAFFIC CONTROL MANAGEMENT =====\n");
        printf("1. Add Vehicle\n");
        printf("2. Display Lane Queues\n");
        printf("3. Manual Traffic Signal\n");
        printf("4. Automatic Traffic Signal\n");
        printf("5. Display Traffic Statistics\n");
        printf("6. Search Vehicle by ID\n");
        printf("7. Exit\n");
        printf("Enter your choice: ");

        if (scanf("%d", &choice) != 1) {
            printf("Invalid input! Restart the program.\n");
            return 1;
        }

        switch (choice) {
            case 1: addVehicle(); break;
            case 2: displayQueues(); break;
            case 3: controlSignal(); break;
            case 4: automaticSignal(); break;
            case 5: displayStatistics(); break;
            case 6: searchVehicle(); break;
            case 7: printf("Exiting program.\n"); break;
            default: printf("Invalid choice!\n");
        }
    } while (choice != 7);

    return 0;
}
