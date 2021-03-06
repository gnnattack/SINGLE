from node_attack.attackTrainerHelpers import (createLogTemplate, setRequiresGrad, train, test, embedRowContinuous)
from classes.basic_classes import Print
from node_attack.attackTrainerTests import test_discrete, test_continuous

import torch
import copy


def attackTrainerContinuous(attack, attacked_nodes: torch.Tensor, y_targets: torch.Tensor,
                            malicious_nodes: torch.Tensor, node_num: int) -> torch.Tensor:
    """
        a trainer function that attacks our model by changing the input attributes
        a successful attack is when we attack successfully AND embed the attributes

        Parameters
        ----------
        attack: oneGNNAttack
        attacked_nodes: torch.Tensor - the victim nodes
        y_targets: torch.Tensor - the target labels of the attack
        malicious_nodes: torch.Tensor - the attacker/malicious node
        node_num: int - the index of the attacked/victim node (out of the train/val/test-set)

        Returns
        -------
        attack_results: torch.Tensor - 2d-tensor that includes
                                       1st-col - the defence
                                       2nd-col - the number of attributes used
        if the number of attributes is 0 the node is misclassified to begin with
    """
    # initialize
    model = attack.model_wrapper.model
    attack_epochs = attack.attack_epochs
    lr = attack.lr
    print_answer = attack.print_answer
    dataset = attack.getDataset()
    data = dataset.data

    num_attributes = data.x.shape[1]
    max_attributes = num_attributes * malicious_nodes.shape[0]

    log_template = createLogTemplate(attack=attack, dataset=dataset)

    # changing the parameters which require grads and setting adversarial optimizer
    optimizer_params = setRequiresGrad(model=model, malicious_nodes=malicious_nodes)
    optimizer = torch.optim.Adam(params=optimizer_params, lr=lr)

    # find best_attributes
    model0 = copy.deepcopy(model)
    prev_changed_attributes = 0
    for epoch in range(0, attack_epochs):
        # train
        train(model=model, targeted=attack.targeted, attacked_nodes=attacked_nodes, y_targets=y_targets,
              optimizer=optimizer)

        # test correctness
        changed_attributes = (model.getInput() != model0.getInput())[malicious_nodes].sum().item()
        test_discrete(model=model, model0=model0, malicious_nodes=malicious_nodes,
                      changed_attributes=changed_attributes, max_attributes=max_attributes)

        # test
        results = test(data=data, model=model, targeted=attack.targeted, attacked_nodes=attacked_nodes,
                       y_targets=y_targets)

        # breaks
        if results[3]:
            # embed
            embeded_model = copy.deepcopy(model)
            for malicious_idx, malicious_node in enumerate(malicious_nodes):
                embedRowContinuous(model=embeded_model, malicious_node=malicious_node, model0=model0,
                                   l_inf=attack.l_inf)

            # test correctness
            changed_attributes = (embeded_model.getInput() != model0.getInput())[malicious_nodes].sum().item()
            test_continuous(model=embeded_model, model0=model0, malicious_nodes=malicious_nodes,
                            changed_attributes=changed_attributes, max_attributes=max_attributes, l_inf=attack.l_inf)
            # test
            results = test(data=data, model=embeded_model, targeted=attack.targeted, attacked_nodes=attacked_nodes,
                           y_targets=y_targets)
            if results[3]:
                if print_answer is Print.YES:
                    print(log_template.format(node_num, epoch + 1, *results[:-1]), flush=True, end='')
                break
        # prints
        if print_answer is Print.YES:
            print(log_template.format(node_num, epoch + 1, *results[:-1]), flush=True, end='')
        if changed_attributes == prev_changed_attributes:
            break
        prev_changed_attributes = changed_attributes

        if epoch != attack_epochs - 1 and print_answer is not Print.NO:
            print()

    if print_answer is Print.YES:
        print(', Attack Success: {}\n'.format(results[-1]), flush=True)
    if not results[3]:
        changed_attributes = max_attributes
    return torch.tensor([[results[3], changed_attributes]]).type(torch.long)
