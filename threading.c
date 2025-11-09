#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <pthread.h>
#include <unistd.h>

void* thread_func(void* arg)
{
    uint16_t thread_num = *(uint16_t*)arg;

    for (uint8_t i = 0; i < 5; i++)
    {
        printf("Thread: %d running\n", thread_num);
        sleep(1);
    }
    printf("Thread: %d finished\n", thread_num);
    return NULL;
}

int32_t main()
{
    uint16_t num_threads = 3;
    pthread_t threads[num_threads];
    uint16_t thread_id[num_threads];
    printf("Creating threads\n");

    for(uint16_t thread_num = 0; thread_num < num_threads; thread_num++)
    {
        thread_id[thread_num] = thread_num + 1;
        if (pthread_create(&threads[thread_num], NULL, thread_func, &thread_id[thread_num]) != 0)
        {
            perror("error creating thread\n");
            return -1;
        }
    }

    printf("main(): threads created, waiting for finish...\n");

    for (uint16_t join_num = 0; join_num < num_threads; join_num++)
    {
        pthread_join(threads[join_num], NULL);
    }

    printf("All threads finished\n");
    return 0;

}

