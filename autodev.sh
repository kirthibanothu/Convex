#!/bin/sh

SESSION_NAME="Convex"

echo "Expected Params: <CODE_PATH> <API_KEY> <API_SECRET> <PASSPHRASE> <IN_DEV> <INSTRUMENT>"
if [ -z "$1" ]
then
    echo "Need to specify repo path - probably /home/<USER>/Development/Convex"
    exit
fi

if [ -z "$2" ]
then
    echo "Need to specify <API_KEY>"
    exit
fi

if [ -z "$3" ]
then
    echo "Need to specify <API_SECRET>"
    exit
fi

if [ -z "$4" ]
then
    echo "Need to specify <PASSPHRASE>"
    exit
fi

if [ -z "$5" ]
then
    echo "Need to specify <IN_DEV> - boolean True / False"
    exit
fi

if [ -z "$6" ]
then
    echo "Need to specify <INSTRUMENT> - ETH / LTC / BTC"
    exit
fi

CONVEX_PATH=$1
API_KEY=$2
API_SECRET=$3
PASSPHRASE=$4
IN_DEV=$5
INSTRUMENT=$6

echo "Starting autodev for Convex with params: [IN DEV: "$IN_DEV"] | [Instrument: "$INSTRUMENT"]"

tmux has-session -t ${SESSION_NAME}

if [ $? != 0 ]
then
    cd $CONVEX_PATH

    # Create a new session
    tmux new-session -s ${SESSION_NAME} -n ConvexDev -d

    # Create Panes
    for i in 0 0 0 2 4 # 4 6
    do
        tmux select-pane -t $i
        tmux split-window -v
    done
    for i in 2 4
    do
        tmux select-pane -t $i
        tmux split-window -h
    done

    # Activate Python Env
    for i in 0 1 2 3 4 5 6 7
    do
        tmux select-pane -t $i
        tmux send-keys "clear" C-m
        tmux send-keys "source venv/bin/activate" C-m
    done

    # Dashboard
    tmux select-pane -t 0
    tmux send-keys "./services/depth_feed.py 0.0.0.0 10 1 "$INSTRUMENT"" C-m

    # Depth Feed
    tmux select-pane -t 1
    tmux send-keys "./services/dashboard.py 0.0.0.0" C-m

    # Git Status
    tmux select-pane -t 2
    tmux send-keys "git status" C-m

    # ls
    tmux select-pane -t 3
    tmux send-keys "ls" C-m


    # Click Trader
    tmux select-pane -t 6
    tmux send-keys "./services/click_trader.py "$API_KEY" "$API_SECRET" "$PASSPHRASE" 0.0.0.0 8003 "$IN_DEV" "$INSTRUMENT" " C-m

    # Strategy 1
    tmux select-pane -t 7
    tmux send-keys "./services/anchor.py "$API_KEY" "$API_SECRET" "$PASSPHRASE" 192.168.0.109 8010 "$IN_DEV" "$INSTRUMENT" "

    # Strategy 2
    #tmux select-pane -t 8
    #tmux send-keys "echo 'Hello!'" C-m

    # Strategy 3
    #tmux select-pane -t 9
    #tmux send-keys "echo 'Hello!'" C-m
fi

tmux attach -t ${SESSION_NAME}
