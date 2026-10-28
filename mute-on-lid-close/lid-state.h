#ifndef LID_STATE_H
#define LID_STATE_H

#include <stdbool.h>

/* An unknown initial state ensures starting with the lid closed also mutes. */
static bool handleLidState(int *previousState, bool closed, bool (*mute)(void))
{
    if (closed && *previousState != 1 && !mute()) {
        return false;
    }
    *previousState = closed ? 1 : 0;
    return true;
}

#endif
